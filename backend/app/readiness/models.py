from pydantic import BaseModel, ConfigDict, Field


class ReadinessComponent(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    detail: str | None = None


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: ReadinessComponent
    database: ReadinessComponent
    schema_state: ReadinessComponent = Field(alias="schema")
    canvas: ReadinessComponent
    last_sync: ReadinessComponent
    last_sync_attempt: ReadinessComponent
    documents: ReadinessComponent
    local_runtime: ReadinessComponent
    local_model: ReadinessComponent
    privacy: ReadinessComponent
