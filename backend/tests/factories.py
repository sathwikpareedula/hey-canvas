from typing import Any


def canvas_course_payload(
    course_id: str | int = "101",
    *,
    name: str = "Autonomous Robots",
    course_code: str = "CSE 4360",
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": course_id,
        "name": name,
        "course_code": course_code,
        "workflow_state": "available",
        "start_at": "2026-08-24T09:00:00-05:00",
        "end_at": "2026-12-10T23:59:59-06:00",
        "updated_at": "2026-09-01T12:30:00Z",
        "term": {
            "id": "2026-fall",
            "name": "Fall 2026",
            "start_at": "2026-08-20T00:00:00-05:00",
            "end_at": "2026-12-20T23:59:59-06:00",
        },
        "enrollments": [
            {
                "type": "StudentEnrollment",
                "enrollment_state": "active",
            }
        ],
    }
    payload.update(overrides)
    return payload


def canvas_assignment_payload(
    assignment_id: str | int = "501",
    *,
    course_id: str | int = "101",
    name: str = "Homework 1",
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": assignment_id,
        "course_id": course_id,
        "name": name,
        "description": "<p>Read <strong>Chapter 1</strong>.</p>",
        "due_at": "2026-10-01T23:59:00-05:00",
        "unlock_at": "2026-09-20T00:00:00-05:00",
        "lock_at": "2026-10-03T23:59:00-05:00",
        "points_possible": 100.0,
        "submission_types": ["online_upload", "online_text_entry"],
        "workflow_state": "published",
        "html_url": "https://canvas.example.edu/courses/101/assignments/501",
        "published": True,
        "has_submitted_submissions": False,
        "updated_at": "2026-09-22T12:30:00Z",
        "rubric": [{"id": "criterion-1", "description": "Correctness", "points": 10}],
    }
    payload.update(overrides)
    return payload


def canvas_module_item_payload(
    item_id: str | int = "1001",
    *,
    module_id: str | int = "201",
    title: str = "Lecture 01.pdf",
    item_type: str = "File",
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": item_id,
        "module_id": module_id,
        "position": 1,
        "title": title,
        "indent": 0,
        "type": item_type,
        "content_id": "7001",
        "html_url": "https://canvas.example.edu/courses/101/modules/items/1001",
        "url": "https://canvas.example.edu/api/v1/courses/101/files/7001",
        "new_tab": False,
        "completion_requirement": {"type": "must_view", "completed": False},
        "content_details": {"locked_for_user": False},
        "published": True,
    }
    payload.update(overrides)
    return payload


def canvas_module_payload(
    module_id: str | int = "201",
    *,
    name: str = "Module 1 — Introduction",
    items: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": module_id,
        "name": name,
        "position": 1,
        "unlock_at": "2026-08-24T00:00:00-05:00",
        "require_sequential_progress": True,
        "requirement_type": "all",
        "publish_final_grade": False,
        "prerequisite_module_ids": [],
        "workflow_state": "active",
        "state": "unlocked",
        "completed_at": None,
        "items_count": len(items) if items is not None else 0,
        "published": True,
        "items": items,
    }
    payload.update(overrides)
    return payload


def canvas_file_payload(
    file_id: Any = "7001",
    *,
    filename: str | None = "lecture-01.pdf",
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": file_id,
        "folder_id": "9001",
        "display_name": filename,
        "filename": filename,
        "content-type": "application/pdf",
        "url": "https://canvas.example.edu/files/7001/download?download_frd=1",
        "size": 12345,
        "created_at": "2026-09-01T12:00:00Z",
        "updated_at": "2026-09-20T13:30:00-05:00",
        "unlock_at": None,
        "lock_at": None,
        "locked": False,
        "hidden": False,
        "hidden_for_user": False,
        "visibility_level": "course",
    }
    payload.update(overrides)
    return payload
