from fastapi import APIRouter, status

from app.api.deps import ProjectServiceDep
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter()


@router.get("", response_model=list[ProjectRead])
async def list_projects(service: ProjectServiceDep) -> list[ProjectRead]:
    return await service.list_all()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, service: ProjectServiceDep) -> ProjectRead:
    return await service.create(body)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: str, service: ProjectServiceDep) -> ProjectRead:
    return await service.get(project_id)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(project_id: str, body: ProjectUpdate, service: ProjectServiceDep) -> ProjectRead:
    return await service.update(project_id, body)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, service: ProjectServiceDep) -> None:
    await service.delete(project_id)
