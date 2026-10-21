"""Collects campaign results so the acceptance report can be generated from a real run."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api.routes import assistant as assistant_routes
from app.assistant_provider.synthetic import SyntheticAcademicModelProvider
from app.database.session import get_session
from app.main import app
from sqlalchemy.orm import Session, sessionmaker

CAMPAIGN_RESULTS: list[dict[str, object]] = []


@pytest.fixture
def install(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    async def no_prepare(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(assistant_routes, "prepare_material_for_request", no_prepare)

    def _install(factory: sessionmaker[Session]) -> None:
        def override() -> Iterator[Session]:
            with factory() as session:
                yield session

        app.dependency_overrides[get_session] = override
        app.dependency_overrides[assistant_routes.get_model_provider] = lambda: (
            SyntheticAcademicModelProvider()
        )

    yield _install
    app.dependency_overrides.clear()


def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    target = os.environ.get("HEY_CANVAS_CAMPAIGN_REPORT")
    if not target or not CAMPAIGN_RESULTS:
        return
    per_feature: dict[str, Counter[str]] = defaultdict(Counter)
    students: set[str] = set()
    for row in CAMPAIGN_RESULTS:
        per_feature[str(row["feature"])]["passed" if row["passed"] else "failed"] += 1
        students.add(str(row["student"]))
    Path(target).write_text(
        json.dumps(
            {
                "students": len(students),
                "cases": len(CAMPAIGN_RESULTS),
                "distinct_cases": len({str(r["case"]) for r in CAMPAIGN_RESULTS}),
                "per_feature": {k: dict(v) for k, v in sorted(per_feature.items())},
                "failures": [r for r in CAMPAIGN_RESULTS if not r["passed"]][:200],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
