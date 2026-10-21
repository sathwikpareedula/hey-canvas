from pydantic import BaseModel, ConfigDict, Field


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=4000)


class BenchmarkResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    provider: str = "synthetic"
    model: str
    success: bool
    timed_out: bool
    first_token_ms: int | None
    total_ms: int
    structured_output_valid: bool
    output: str = Field(max_length=4000)
    error: str | None = None
