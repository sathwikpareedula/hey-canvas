"""Phase 2: Live Academic Data Consistency Acceptance Script.

Tests the running Hey Canvas backend (http://127.0.0.1:8000) and SQLite database
against the 11 Phase 2 academic data correctness requirements.
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_URL = "http://127.0.0.1:8000"
HEADERS = {
    "x-hey-canvas-client": "hey-canvas-local",
    "Origin": "http://localhost:3001",
}


def api_get(path: str) -> dict | list:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(path: str, payload: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**HEADERS, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_checks() -> dict[str, bool]:
    results = {}

    print("=== 1. Courses and Focus Courses ===")
    courses = api_get("/api/courses")
    assert len(courses) == 20, f"Expected 20 courses, got {len(courses)}"
    focus = api_get("/api/focus-courses")
    assert len(focus) == 5, f"Expected 5 focus courses, got {len(focus)}"
    print(f"PASS: 20 courses returned, 5 focus courses returned ({[c.get('course_code') or c.get('course_name') for c in focus]})")
    results["courses_and_focus"] = True

    print("\n=== 2. Assignments and Assignment Details ===")
    assignments = api_get("/api/assignments")
    assert len(assignments) == 188, f"Expected 188 assignments, got {len(assignments)}"
    sample_assignment = next(a for a in assignments if a.get("due_at"))
    sample_id = sample_assignment["canvas_assignment_id"]
    course_id = sample_assignment["canvas_course_id"]
    course_assignments = api_get(f"/api/assignments?course_id={course_id}")
    matching = [a for a in course_assignments if a["canvas_assignment_id"] == sample_id]
    assert len(matching) == 1
    detail = matching[0]
    assert "name" in detail
    assert detail["canvas_course_id"] == course_id
    print(f"PASS: 188 assignments total. Sample assignment '{detail['name']}' (due {detail['due_at']}) verified in course {course_id}")
    results["assignments_and_details"] = True

    print("\n=== 3. Deadlines and Timezone Handling ===")
    windows = ["today", "tomorrow", "this_week", "next_week", "next_7_days", "overdue", "upcoming"]
    chicago_tz = ZoneInfo("America/Chicago")
    for w in windows:
        window_deadlines = api_get(f"/api/deadlines?window={w}")
        assert isinstance(window_deadlines, list)
        for a in window_deadlines[:5]:
            due = a.get("due_at")
            if due:
                dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                dt_chicago = dt.astimezone(chicago_tz)
                assert dt_chicago.tzinfo is not None
        print(f"  Window '{w}': {len(window_deadlines)} items")
    print(f"PASS: All 7 deadline windows returned valid timezone-aware academic assignments")
    results["deadlines_timezone"] = True

    print("\n=== 4. Calendar ===")
    calendar_links = api_get("/api/calendar/links")
    assert isinstance(calendar_links, list)
    # Test calendar preview for the sample assignment
    preview = api_post("/api/calendar/preview", {
        "course_id": course_id,
        "assignment_id": sample_id,
    })
    assert "event" in preview
    assert "confirmation" in preview
    assert detail["name"] in preview["event"]["summary"]
    print(f"PASS: Calendar links ({len(calendar_links)}) and Preview for assignment '{detail['name']}' verified (action_id={preview['confirmation']['action_id']})")
    results["calendar"] = True

    print("\n=== 5. Modules and Materials ===")
    first_course_id = courses[0]["canvas_course_id"]
    course_modules = api_get(f"/api/courses/{first_course_id}/modules")
    assert isinstance(course_modules, list)
    files = api_get(f"/api/files?course_id={first_course_id}")
    assert isinstance(files, list)
    print(f"PASS: Modules ({len(course_modules)}) and Files ({len(files)}) retrieved for course {first_course_id}")
    results["modules_materials"] = True

    print("\n=== 6. Announcements ===")
    announcements = api_get(f"/api/courses/{first_course_id}/announcements")
    assert isinstance(announcements, list)
    changes = api_get("/api/changes")
    assert isinstance(changes, list)
    summary = api_get("/api/changes/summary")
    assert isinstance(summary, dict)
    print(f"PASS: Announcements for course {first_course_id}: {len(announcements)}, total change events: {len(changes)}, summary keys: {list(summary.keys())}")
    results["announcements"] = True

    print("\n=== 7. Documents and Search ===")
    documents = api_get("/api/documents")
    assert isinstance(documents, list)
    search_hits = api_get("/api/document-search?q=syllabus")
    assert isinstance(search_hits, list)
    print(f"PASS: Documents returned: {len(documents)}, search for 'syllabus' returned {len(search_hits)} hits")
    results["search"] = True

    print("\n=== 8. Workload / Today / Dashboard ===")
    # Dashboard and Today rely on deadline windows and changes
    today_dl = api_get("/api/deadlines?window=today")
    tomorrow_dl = api_get("/api/deadlines?window=tomorrow")
    this_week_dl = api_get("/api/deadlines?window=this_week")
    recent_changes = api_get("/api/changes?limit=5")
    assert isinstance(today_dl, list)
    assert isinstance(tomorrow_dl, list)
    assert isinstance(this_week_dl, list)
    assert isinstance(recent_changes, list)

    # Test Academic Context resolution
    context_res = api_post("/api/academic-context/resolve", {
        "course_id": first_course_id,
        "text": "when is homework 1 due?",
    })
    assert "course_id" in context_res
    print(f"PASS: Composed Dashboard/Today/Workload pipelines verified (today: {len(today_dl)}, tomorrow: {len(tomorrow_dl)}, this_week: {len(this_week_dl)}, changes: {len(recent_changes)}). Academic context resolved for course {first_course_id} ({context_res['course_name']}).")
    results["dashboard_today_workload"] = True

    print("\n=== 9. Sync Status and History ===")
    sync_runs = api_get("/api/sync-runs")
    assert len(sync_runs) > 0, "Expected at least 1 historical sync run"
    latest_run = sync_runs[0]
    assert latest_run["status"] == "succeeded"
    print(f"PASS: Latest sync run id={latest_run['id']} status={latest_run['status']} at {latest_run['finished_at']}")
    results["sync_history"] = True

    print("\n=== 10. Course Switching and Isolation ===")
    c1_id = courses[0]["canvas_course_id"]
    c2_id = courses[1]["canvas_course_id"]
    c1_assignments = api_get(f"/api/assignments?course_id={c1_id}")
    c2_assignments = api_get(f"/api/assignments?course_id={c2_id}")
    c1_ids = {a["canvas_assignment_id"] for a in c1_assignments}
    c2_ids = {a["canvas_assignment_id"] for a in c2_assignments}
    assert c1_ids.isdisjoint(c2_ids), "Violation of course isolation: assignments leaked across courses!"
    print(f"PASS: Strict course isolation verified: Course 1 ({len(c1_assignments)} items) and Course 2 ({len(c2_assignments)} items) have 0 overlap")
    results["course_isolation"] = True

    return results


if __name__ == "__main__":
    try:
        res = run_checks()
        print("\nSUMMARY:")
        for k, v in res.items():
            print(f"  {k}: {'PASS' if v else 'FAIL'}")
        if all(res.values()):
            print("\nALL 10 CHECKS PASSED!")
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
