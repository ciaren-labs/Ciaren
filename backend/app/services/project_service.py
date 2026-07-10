# SPDX-License-Identifier: AGPL-3.0-only
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.dataset import Dataset
from app.db.models.flow import DISABLED_BY_PROJECT, Flow
from app.db.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate


class ProjectService:
    """Manages the lightweight project/workspace layer.

    Every dataset and flow belongs to exactly one project. The first time the
    service is used it lazily creates (and backfills into) a ``Default`` project
    so existing data is never orphaned.
    """

    DEFAULT_NAME = "Default"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ensure_default(self) -> Project:
        """Return the default project, creating it (and adopting orphaned
        datasets/flows) on first call. Idempotent."""
        result = await self.db.execute(select(Project).where(Project.is_default.is_(True)))
        project = result.scalar_one_or_none()
        if project is not None:
            return project

        project = Project(
            name=self.DEFAULT_NAME,
            description="Your default workspace.",
            color="violet",
            is_default=True,
        )
        self.db.add(project)
        await self.db.flush()  # assign project.id
        # Adopt any pre-existing rows that have no project yet.
        await self.db.execute(update(Dataset).where(Dataset.project_id.is_(None)).values(project_id=project.id))
        await self.db.execute(update(Flow).where(Flow.project_id.is_(None)).values(project_id=project.id))
        await self.db.commit()
        return project

    async def list_all(self) -> list[ProjectRead]:
        await self.ensure_default()
        result = await self.db.execute(select(Project).order_by(Project.created_at.asc()))
        projects = list(result.scalars().all())
        dataset_counts = await self._counts(Dataset)
        flow_counts = await self._counts(Flow)
        return [self._to_read(p, dataset_counts.get(p.id, 0), flow_counts.get(p.id, 0)) for p in projects]

    async def get(self, project_id: str) -> ProjectRead:
        project = await self._get_or_raise(project_id)
        dataset_counts = await self._counts(Dataset)
        flow_counts = await self._counts(Flow)
        return self._to_read(project, dataset_counts.get(project.id, 0), flow_counts.get(project.id, 0))

    async def create(self, data: ProjectCreate) -> ProjectRead:
        await self._ensure_name_free(data.name)
        project = Project(name=data.name, description=data.description, color=data.color)
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return self._to_read(project, 0, 0)

    async def update(self, project_id: str, data: ProjectUpdate) -> ProjectRead:
        project = await self._get_or_raise(project_id)
        updates = data.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] != project.name:
            await self._ensure_name_free(updates["name"])
        for field, value in updates.items():
            setattr(project, field, value)
        project.updated_at = datetime.now(UTC).replace(tzinfo=None)
        # Cascade is_disabled to the datasets and flows in this project, tagging a
        # reason so re-enabling restores only what the project cascade disabled.
        if "is_disabled" in updates:
            disabled = updates["is_disabled"]
            await self._cascade_dataset_disable(project_id, disabled)
            await self._cascade_flow_disable(project_id, disabled)
        await self.db.commit()
        await self.db.refresh(project)
        return await self.get(project.id)

    async def delete(self, project_id: str) -> None:
        """Delete a project, reassigning its datasets/flows to the default."""
        project = await self._get_or_raise(project_id)
        if project.is_default:
            raise ValidationError("The default project cannot be deleted.")
        default = await self.ensure_default()
        await self.db.execute(update(Dataset).where(Dataset.project_id == project_id).values(project_id=default.id))
        await self.db.execute(update(Flow).where(Flow.project_id == project_id).values(project_id=default.id))
        await self.db.delete(project)
        await self.db.commit()

    async def resolve_id(self, project_id: str | None) -> str:
        """Return a valid project id, falling back to the default when ``None``."""
        if project_id is not None:
            await self._get_or_raise(project_id)
            return project_id
        return (await self.ensure_default()).id

    async def _cascade_dataset_disable(self, project_id: str, disabled: bool) -> None:
        """Propagate the project's state to its datasets, reason-tagged like flows.

        Disabling tags only currently-enabled datasets ``DISABLED_BY_PROJECT`` and
        records *this* project as the origin (``disabled_by_project_id``); re-enabling
        restores only rows both reason- and origin-tagged to this project (never a
        soft-deleted one — ``deleted_at`` is an independent, stronger state). A row
        that was disabled by this project and then moved to another project (or whose
        origin project was deleted and it was reassigned to Default) keeps its stale
        origin id forever, so it is never wrongly revived by an unrelated project's
        cascade — it stays disabled until re-enabled directly. A dataset the user
        disabled directly, or one that is soft-deleted, is left untouched."""
        if disabled:
            stmt = (
                update(Dataset)
                .where(Dataset.project_id == project_id, Dataset.is_disabled.is_(False))
                .values(is_disabled=True, disabled_reason=DISABLED_BY_PROJECT, disabled_by_project_id=project_id)
            )
        else:
            stmt = (
                update(Dataset)
                .where(
                    Dataset.project_id == project_id,
                    Dataset.disabled_reason == DISABLED_BY_PROJECT,
                    Dataset.disabled_by_project_id == project_id,
                    Dataset.deleted_at.is_(None),
                )
                .values(is_disabled=False, disabled_reason=None, disabled_by_project_id=None)
            )
        await self.db.execute(stmt)

    async def _cascade_flow_disable(self, project_id: str, disabled: bool) -> None:
        """Propagate a project's enabled/disabled state to its flows without
        clobbering flows disabled for their own reasons.

        Disabling tags only the *currently-enabled* flows as ``DISABLED_BY_PROJECT``
        and records *this* project as the origin (``disabled_by_project_id``) — a flow
        already disabled by the user or a broken dependency keeps its own reason.
        Re-enabling restores *only* flows both reason- and origin-tagged to this
        project — a manually- or dependency-disabled flow stays disabled, as it
        should, and so does one this project disabled but that has since moved to
        (or was reassigned to, via project delete) a different project."""
        if disabled:
            stmt = (
                update(Flow)
                .where(Flow.project_id == project_id, Flow.is_disabled.is_(False))
                .values(is_disabled=True, disabled_reason=DISABLED_BY_PROJECT, disabled_by_project_id=project_id)
            )
        else:
            stmt = (
                update(Flow)
                .where(
                    Flow.project_id == project_id,
                    Flow.disabled_reason == DISABLED_BY_PROJECT,
                    Flow.disabled_by_project_id == project_id,
                )
                .values(is_disabled=False, disabled_reason=None, disabled_by_project_id=None)
            )
        await self.db.execute(stmt)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _to_read(self, project: Project, dataset_count: int, flow_count: int) -> ProjectRead:
        return ProjectRead(
            id=project.id,
            name=project.name,
            description=project.description,
            color=project.color,
            is_default=project.is_default,
            is_disabled=bool(project.is_disabled),
            dataset_count=dataset_count,
            flow_count=flow_count,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def _counts(self, model: type[Dataset] | type[Flow]) -> dict[str, int]:
        result = await self.db.execute(select(model.project_id, func.count()).group_by(model.project_id))
        return {pid: count for pid, count in result.all() if pid is not None}

    async def _ensure_name_free(self, name: str) -> None:
        result = await self.db.execute(select(Project).where(func.lower(Project.name) == name.lower()))
        if result.scalar_one_or_none() is not None:
            raise ConflictError(f"A project named '{name}' already exists.")

    async def _get_or_raise(self, project_id: str) -> Project:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project", project_id)
        return project
