"""Local provenance-aware retrieval diagnostic command."""

import argparse
import json
import sys

from app.canvas.courses import _normalize_canvas_id
from app.config import get_settings
from app.database.session import get_session_factory, initialize_database
from app.logging import configure_logging
from app.services.retrieval import RetrievalService
from app.services.retrieval_context import RetrievalContextPackager


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Search locally parsed academic units with provenance"
    )
    parser.add_argument("query")
    parser.add_argument("--course-id")
    parser.add_argument("--file-id")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--mode", choices=("lexical", "semantic", "hybrid"), default="lexical")
    parser.add_argument("--context-package", action="store_true")
    parser.add_argument("--max-context-characters", type=int, default=12_000)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if not 1 <= args.max_context_characters <= 100_000:
        parser.error("--max-context-characters must be between 1 and 100000")
    try:
        course_id = (
            _normalize_canvas_id(args.course_id, field_name="course_id")
            if args.course_id
            else None
        )
        file_id = (
            _normalize_canvas_id(args.file_id, field_name="file_id")
            if args.file_id
            else None
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_database()
    with get_session_factory()() as session:
        response = RetrievalService(session).search(
            args.query,
            canvas_course_id=course_id,
            canvas_file_id=file_id,
            limit=args.limit,
            mode=args.mode,
        )
    payload = (
        RetrievalContextPackager()
        .package(
            response,
            max_characters=args.max_context_characters,
            max_items=args.limit,
        )
        .model_dump(mode="json")
        if args.context_package
        else response.model_dump(mode="json")
    )
    json.dump(payload, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
