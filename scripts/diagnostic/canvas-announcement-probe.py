"""Read-only probe: compare Canvas announcement topic counts (no secrets printed)."""
from __future__ import annotations

import asyncio
import json
import sys

import httpx

from app.canvas.client import CanvasClient
from app.config import get_settings


async def _count_topics(client: CanvasClient, course_id: str, **params: str) -> int:
    from urllib.parse import quote

    encoded = quote(course_id, safe="~")
    payloads = await client.get_paginated(
        f"/api/v1/courses/{encoded}/discussion_topics",
        params=httpx.QueryParams({**params, "per_page": "100"}),
    )
    return len(payloads)


async def main() -> int:
    settings = get_settings()
    if not settings.canvas_base_url or settings.canvas_token is None:
        print(json.dumps({"error": "canvas_not_configured"}))
        return 1
    course_id = sys.argv[1] if len(sys.argv) > 1 else "278791"
    async with CanvasClient(
        base_url=settings.canvas_base_url,
        token=settings.canvas_token,
    ) as client:
        only_ann = await _count_topics(
            client, course_id, only_announcements="true"
        )
        all_topics = await _count_topics(client, course_id)
    print(
        json.dumps(
            {
                "canvas_course_id": course_id,
                "discussion_topics_only_announcements": only_ann,
                "discussion_topics_all": all_topics,
                "conclusion": (
                    "no_announcement_topics_on_canvas"
                    if only_ann == 0
                    else "announcements_present"
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
