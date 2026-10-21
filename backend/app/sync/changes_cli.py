"""Local-only CLI for deterministic academic change history."""

import argparse
import json
import sys
from datetime import datetime

from app.config import get_settings
from app.database.session import get_session_factory, initialize_database
from app.logging import configure_logging
from app.services.change_query import ChangeQueryService


def _aware_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset")
    return parsed


def run() -> int:
    parser = argparse.ArgumentParser(description="Read local academic change events")
    parser.add_argument("--course-id")
    parser.add_argument("--entity-type")
    parser.add_argument("--event-type")
    parser.add_argument("--since", type=_aware_timestamp)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 500:
        parser.error("--limit must be between 1 and 500")
    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_database()
    with get_session_factory()() as session:
        events = ChangeQueryService(session).list_changes(
            course_id=args.course_id,
            entity_type=args.entity_type,
            event_type=args.event_type,
            since=args.since,
            limit=args.limit,
        )
    json.dump([event.model_dump(mode="json") for event in events], sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
