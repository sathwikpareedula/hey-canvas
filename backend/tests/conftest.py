import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Windows: avoid PermissionError on system Temp pytest basetemp.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYTEST_TMP = _REPO_ROOT / ".hey-canvas" / "pytest-tmp"
_PYTEST_TMP.mkdir(parents=True, exist_ok=True)
# These values are intentionally assigned (not setdefault): pytest must never
# inherit live Canvas credentials, a user's DPAPI store, or a real provider
# from the shell or repository .env file.
os.environ["TMP"] = str(_PYTEST_TMP)
os.environ["TEMP"] = str(_PYTEST_TMP)
os.environ["APP_ENV"] = "test"
os.environ["CANVAS_BASE_URL"] = ""
os.environ["CANVAS_TOKEN"] = ""
os.environ["ACADEMIC_MODEL_PROVIDER"] = "synthetic"
os.environ["DATABASE_URL"] = (
    f"sqlite:///{(_PYTEST_TMP / f'app-{os.getpid()}.db').as_posix()}"
)
os.environ["ACADEMIC_FILES_ROOT"] = str(_PYTEST_TMP / f"files-{os.getpid()}")
os.environ["HEY_CANVAS_CREDENTIAL_STORE"] = str(
    _PYTEST_TMP / f"credential-store-{os.getpid()}.json"
)
os.environ["LOCAL_API_GUARD_ENABLED"] = "false"
# These imports intentionally follow the Windows temp override above.
from app.database.models import Base
from app.database.session import enable_sqlite_foreign_keys
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(autouse=True)
def _disable_local_api_guard_by_default(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Ordinary TestClient suites use synthetic hosts; adversarial suites opt in."""
    if request.module.__name__.endswith("test_guard_adversarial"):
        return
    monkeypatch.setenv("LOCAL_API_GUARD_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def database_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'academic-test.db'}",
        connect_args={"check_same_thread": False},
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(database_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=database_engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as database_session:
        yield database_session
