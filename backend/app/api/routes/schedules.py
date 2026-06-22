from fastapi import APIRouter, status

from app.api.deps import ScheduleServiceDep
from app.schemas.run import FlowRunRead
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate

router = APIRouter()


@router.post(
    "/flows/{flow_id}/schedules",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    flow_id: str, body: ScheduleCreate, service: ScheduleServiceDep
) -> ScheduleRead:
    return await service.create(flow_id, body)


@router.get("/flows/{flow_id}/schedules", response_model=list[ScheduleRead])
async def list_flow_schedules(flow_id: str, service: ScheduleServiceDep) -> list[ScheduleRead]:
    return await service.list_schedules(flow_id=flow_id)


@router.get("/schedules", response_model=list[ScheduleRead])
async def list_schedules(
    service: ScheduleServiceDep, flow_id: str | None = None
) -> list[ScheduleRead]:
    return await service.list_schedules(flow_id=flow_id)


@router.get("/schedules/{schedule_id}", response_model=ScheduleRead)
async def get_schedule(schedule_id: str, service: ScheduleServiceDep) -> ScheduleRead:
    return await service.get(schedule_id)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleRead)
async def update_schedule(
    schedule_id: str, body: ScheduleUpdate, service: ScheduleServiceDep
) -> ScheduleRead:
    return await service.update(schedule_id, body)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: str, service: ScheduleServiceDep) -> None:
    await service.delete(schedule_id)


@router.post(
    "/schedules/{schedule_id}/run-now",
    response_model=FlowRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def run_schedule_now(schedule_id: str, service: ScheduleServiceDep) -> FlowRunRead:
    return await service.run_now(schedule_id)
