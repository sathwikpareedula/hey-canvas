"""Local-only selected-model persistence."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import LocalAISetting
from app.local_ai.models import LocalModelSelection


class LocalAISettingsService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        user_key: str = "local-user",
    ) -> None:
        if not user_key or len(user_key) > 100:
            raise ValueError("user_key is invalid")
        self._session = session
        self._settings = settings
        self._user_key = user_key

    def selection(self) -> LocalModelSelection:
        record = self._record()
        if record is None:
            return LocalModelSelection(
                model=self._settings.ollama_model,
                source="environment_default",
            )
        return LocalModelSelection(
            model=record.selected_model,
            source="saved",
            updated_at=record.updated_at,
        )

    def select(self, model: str, *, installed_models: tuple[str, ...]) -> LocalModelSelection:
        normalized = _normalize_model_name(model)
        if normalized not in installed_models:
            raise LookupError("selected model is not installed")
        record = self._record()
        now = datetime.now(UTC)
        if record is None:
            record = LocalAISetting(
                user_key=self._user_key,
                selected_model=normalized,
                updated_at=now,
            )
            self._session.add(record)
        else:
            record.selected_model = normalized
            record.updated_at = now
        self._session.commit()
        return self.selection()

    def _record(self) -> LocalAISetting | None:
        return self._session.scalar(
            select(LocalAISetting).where(LocalAISetting.user_key == self._user_key)
        )


def _normalize_model_name(model: str) -> str:
    normalized = model.strip()
    if not normalized or len(normalized) > 255:
        raise ValueError("model name is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError("model name is invalid")
    return normalized


def resolve_installed_model_name(selected: str, installed_models: tuple[str, ...]) -> str:
    """Resolve an omitted Ollama tag only when one installed identity is unambiguous."""

    normalized = _normalize_model_name(selected)
    if normalized in installed_models:
        return normalized
    base = normalized.split(":", 1)[0]
    matches = tuple(model for model in installed_models if model.split(":", 1)[0] == base)
    return matches[0] if len(matches) == 1 else normalized
