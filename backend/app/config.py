"""Application configuration loaded from environment variables and local `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings.

    Canvas credentials are optional so local health checks and automated tests never
    require access to a real Canvas account.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    hey_canvas_data_dir: Path | None = None
    database_url: str = "sqlite:///./data/uta_academic_copilot.db"
    academic_timezone: str = "America/Chicago"
    academic_files_root: Path = Path("data/files")
    max_canvas_file_bytes: int = 100 * 1024 * 1024
    canvas_file_metadata_concurrency: int = 5
    sync_run_stale_minutes: int = 30
    max_document_characters: int = 2_000_000
    max_document_units: int = 2_000
    max_document_unit_characters: int = 100_000
    max_document_archive_entries: int = 5_000
    max_document_archive_uncompressed_bytes: int = 200 * 1024 * 1024
    max_document_archive_ratio: int = 200
    knowledge_max_download_files_per_sync: int = 25
    knowledge_max_download_bytes_per_sync: int = 100 * 1024 * 1024
    canvas_base_url: str | None = None
    canvas_token: SecretStr | None = None
    academic_model_provider: Literal["synthetic", "ollama"] = "synthetic"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_num_predict: int = 256
    ollama_context_length: int = 4096
    ollama_keep_alive_seconds: int = 600
    assistant_request_timeout_seconds: float = 180.0
    assistant_blocking_workers: int = 2
    ollama_max_concurrent_requests: int = 1
    ollama_queue_wait_seconds: float = 45.0
    api_bind_host: str = "127.0.0.1"
    api_allow_remote_bind: bool = False
    local_api_guard_enabled: bool = True
    local_api_max_body_bytes: int = 512_000
    local_api_allowed_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:13117,http://127.0.0.1:13117"
    )

    @model_validator(mode="after")
    def apply_data_dir(self) -> "Settings":
        if self.hey_canvas_data_dir is not None:
            resolved_dir = self.hey_canvas_data_dir.expanduser().resolve()
            if self.database_url == "sqlite:///./data/uta_academic_copilot.db":
                db_target = resolved_dir / "uta_academic_copilot.db"
                object.__setattr__(self, "database_url", f"sqlite:///{db_target.as_posix()}")
            if self.academic_files_root == Path("data/files"):
                object.__setattr__(self, "academic_files_root", resolved_dir / "files")
        return self

    @field_validator("academic_model_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        allowed = {"synthetic", "ollama"}
        if value not in allowed:
            raise ValueError("ACADEMIC_MODEL_PROVIDER must be synthetic or ollama")
        return value

    @field_validator("assistant_request_timeout_seconds")
    @classmethod
    def validate_provider_timeout(cls, value: float) -> float:
        if value <= 0 or value > 300:
            raise ValueError("ASSISTANT_REQUEST_TIMEOUT_SECONDS must be between 0 and 300 seconds")
        return value

    @field_validator("ollama_num_predict")
    @classmethod
    def validate_ollama_num_predict(cls, value: int) -> int:
        if value < 32 or value > 900:
            raise ValueError("OLLAMA_NUM_PREDICT must be between 32 and 900")
        return value

    @field_validator("ollama_context_length")
    @classmethod
    def validate_ollama_context_length(cls, value: int) -> int:
        if value < 2048 or value > 32768:
            raise ValueError("OLLAMA_CONTEXT_LENGTH must be between 2048 and 32768")
        return value

    @field_validator("ollama_keep_alive_seconds")
    @classmethod
    def validate_ollama_keep_alive_seconds(cls, value: int) -> int:
        if value < 0 or value > 3600:
            raise ValueError("OLLAMA_KEEP_ALIVE_SECONDS must be between 0 and 3600")
        return value

    @field_validator("assistant_blocking_workers")
    @classmethod
    def validate_blocking_workers(cls, value: int) -> int:
        if value < 1 or value > 8:
            raise ValueError("ASSISTANT_BLOCKING_WORKERS must be between 1 and 8")
        return value

    @field_validator("ollama_max_concurrent_requests")
    @classmethod
    def validate_ollama_concurrency(cls, value: int) -> int:
        if value < 1 or value > 2:
            raise ValueError("OLLAMA_MAX_CONCURRENT_REQUESTS must be 1 or 2")
        return value

    @field_validator("ollama_queue_wait_seconds")
    @classmethod
    def validate_ollama_queue_wait(cls, value: float) -> float:
        if value <= 0 or value > 120:
            raise ValueError("OLLAMA_QUEUE_WAIT_SECONDS must be between 0 and 120 seconds")
        return value

    @field_validator("academic_timezone")
    @classmethod
    def validate_academic_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("ACADEMIC_TIMEZONE must be a valid IANA timezone") from exc
        return value

    @field_validator("max_canvas_file_bytes")
    @classmethod
    def validate_max_canvas_file_bytes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_CANVAS_FILE_BYTES must be positive")
        return value

    @field_validator("canvas_file_metadata_concurrency")
    @classmethod
    def validate_file_concurrency(cls, value: int) -> int:
        if not 1 <= value <= 20:
            raise ValueError("CANVAS_FILE_METADATA_CONCURRENCY must be between 1 and 20")
        return value

    @field_validator("sync_run_stale_minutes")
    @classmethod
    def validate_sync_run_stale_minutes(cls, value: int) -> int:
        if not 1 <= value <= 1440:
            raise ValueError("SYNC_RUN_STALE_MINUTES must be between 1 and 1440")
        return value

    @field_validator(
        "max_document_characters",
        "max_document_units",
        "max_document_unit_characters",
        "max_document_archive_entries",
        "max_document_archive_uncompressed_bytes",
        "max_document_archive_ratio",
    )
    @classmethod
    def validate_document_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("document resource limits must be positive")
        return value

    @field_validator("knowledge_max_download_files_per_sync")
    @classmethod
    def validate_knowledge_file_limit(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("KNOWLEDGE_MAX_DOWNLOAD_FILES_PER_SYNC must be between 0 and 100")
        return value

    @field_validator("knowledge_max_download_bytes_per_sync")
    @classmethod
    def validate_knowledge_byte_limit(cls, value: int) -> int:
        if not 0 <= value <= 500 * 1024 * 1024:
            raise ValueError(
                "KNOWLEDGE_MAX_DOWNLOAD_BYTES_PER_SYNC must be between 0 and 524288000"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide settings instance."""

    return Settings()
