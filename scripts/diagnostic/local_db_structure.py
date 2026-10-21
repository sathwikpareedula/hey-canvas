"""Structural counts only — no course content printed."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app.database.models import (
    AcademicDocument,
    Assignment,
    Course,
    DocumentUnit,
    StudyContext,
)
from app.database.session import enable_sqlite_foreign_keys
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".hey-canvas" / "run" / "local-db-structure.json"


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./data/uta_academic_copilot.db")
    if db_url.startswith("sqlite:///./"):
        path = ROOT / db_url.removeprefix("sqlite:///./")
        db_url = f"sqlite:///{path.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    enable_sqlite_foreign_keys(engine)
    summary: dict[str, int | bool] = {
        "database_exists": Path(db_url.replace("sqlite:///", "")).exists()
    }
    with Session(engine) as session:
        summary["courses"] = session.scalar(select(func.count()).select_from(Course)) or 0
        summary["assignments"] = session.scalar(select(func.count()).select_from(Assignment)) or 0
        summary["documents"] = (
            session.scalar(select(func.count()).select_from(AcademicDocument)) or 0
        )
        summary["document_units"] = (
            session.scalar(select(func.count()).select_from(DocumentUnit)) or 0
        )
        summary["study_contexts"] = (
            session.scalar(select(func.count()).select_from(StudyContext)) or 0
        )
        summary["has_focus_candidates"] = summary["courses"] > 0
        summary["has_assignments"] = summary["assignments"] > 0
        summary["has_indexed_units"] = summary["document_units"] > 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
