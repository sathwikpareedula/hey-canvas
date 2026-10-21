from pydantic import BaseModel, ConfigDict, Field


class LifecycleScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_key: str | None = Field(default=None, max_length=255)
    course_id: str | None = Field(default=None, max_length=255)
    include_study_state: bool = False
    include_materials: bool = False


class LifecycleResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_deleted: bool
    study_sessions_deleted: int
    practice_sessions_deleted: int
    materials_marked_for_removal: int
