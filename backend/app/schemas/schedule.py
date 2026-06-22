from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    cron: str = Field(..., min_length=1, max_length=255)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    timezone: str = Field("UTC", max_length=64)
    # None falls back to the server's DEFAULT_ENGINE when the run fires.
    engine: str | None = None
    input_dataset_id: str | None = None
    enabled: bool = True
    catch_up: bool = False


class ScheduleUpdate(BaseModel):
    cron: str | None = Field(None, min_length=1, max_length=255)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    timezone: str | None = Field(None, max_length=64)
    engine: str | None = None
    input_dataset_id: str | None = None
    enabled: bool | None = None
    catch_up: bool | None = None


class ScheduleRead(BaseModel):
    id: str
    flow_id: str
    name: str | None
    description: str | None
    cron: str
    timezone: str
    engine: str | None
    input_dataset_id: str | None
    enabled: bool
    catch_up: bool
    next_run_at: datetime | None
    last_fired_at: datetime | None
    last_run_id: str | None
    last_status: str | None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
