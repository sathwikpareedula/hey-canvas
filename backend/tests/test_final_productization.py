from datetime import UTC, datetime

import pytest
from app.benchmarks.models import BenchmarkCase
from app.benchmarks.service import BenchmarkService
from app.config import Settings
from app.database.models import Course, SchemaVersion, SyncRun
from app.lifecycle.models import LifecycleScope
from app.lifecycle.service import LifecycleService
from app.privacy.models import (
    CourseAIPolicyUpdate,
    CourseAIPolicyValue,
    PrivacyMode,
    PrivacySettingsUpdate,
)
from app.privacy.service import PrivacyService
from app.readiness.service import ReadinessService


def add_course(session, course_id: str) -> None:
    now = datetime.now(UTC)
    session.add(
        Course(
            canvas_course_id=course_id,
            course_name=course_id,
            workflow_state="available",
            enrollment_state="active",
            first_seen_at=now,
            last_seen_at=now,
            last_synced_at=now,
        )
    )
    session.commit()


def test_privacy_defaults_local_and_course_policy_is_unknown(session) -> None:
    add_course(session, "course-1")
    service = PrivacyService(session)
    assert service.settings().mode is PrivacyMode.LOCAL_ONLY
    assert service.policy("course-1").policy is CourseAIPolicyValue.UNKNOWN
    updated = service.update_settings(PrivacySettingsUpdate(mode=PrivacyMode.OPTIONAL_CLOUD_BYO))
    assert updated.mode is PrivacyMode.OPTIONAL_CLOUD_BYO
    policy = service.set_policy(
        "course-1",
        CourseAIPolicyUpdate(
            policy=CourseAIPolicyValue.RESTRICTED,
            provider_mode=PrivacyMode.LOCAL_ONLY,
            notes="keep course material local",
        ),
    )
    assert policy.policy is CourseAIPolicyValue.RESTRICTED


def test_privacy_and_workspace_state_are_owner_scoped(session) -> None:
    add_course(session, "course-1")
    owner = PrivacyService(session, user_key="owner-a")
    other = PrivacyService(session, user_key="owner-b")
    owner.set_policy("course-1", CourseAIPolicyUpdate(policy=CourseAIPolicyValue.DISABLED))
    assert other.policy("course-1").policy is CourseAIPolicyValue.UNKNOWN


def test_benchmark_records_failures_without_quality_score() -> None:
    service = BenchmarkService(
        model_name="fixture",
        runner=lambda prompt: prompt,
    )
    result = service.run((BenchmarkCase(case_id="missing-evidence", prompt="No source"),))[0]
    assert result.success
    assert result.total_ms >= 0
    assert result.structured_output_valid is False


def test_benchmark_records_timeout() -> None:
    def timeout(_: str) -> str:
        raise TimeoutError

    result = BenchmarkService(model_name="fixture", runner=timeout).run(
        (BenchmarkCase(case_id="slow", prompt="wait"),)
    )[0]
    assert result.timed_out
    assert result.error == "timeout"


def test_lifecycle_requires_explicit_scope(session) -> None:
    with pytest.raises(ValueError):
        LifecycleService(session).clear(LifecycleScope())


def test_readiness_is_credential_free_and_reports_schema(session) -> None:
    session.add(SchemaVersion(version=1, applied_at=datetime.now(UTC)))
    session.commit()
    response = ReadinessService(session, Settings(_env_file=None)).check()
    assert response.schema_state.status == "ready"
    assert response.canvas.status == "not_configured"


def test_readiness_separates_cached_sync_from_unchecked_canvas(session) -> None:
    now = datetime.now(UTC)
    session.add(
        SyncRun(
            started_at=now,
            finished_at=now,
            heartbeat_at=now,
            status="succeeded",
            trigger="manual",
            scope_course_ids=[],
            check_local_files=False,
            active_lock_key=None,
            stage_results={},
            change_summary={},
            change_events_created=0,
            error_count=0,
            errors=[],
            created_at=now,
        )
    )
    session.commit()

    response = ReadinessService(
        session,
        Settings(
            _env_file=None,
            canvas_base_url="https://canvas.example.edu",
            canvas_token="test-token",
        ),
    ).check()

    assert response.canvas.status == "unknown"
    assert response.canvas.detail == "configured; live availability not checked"
    assert response.last_sync.status == "ready"
    assert response.last_sync.detail == now.isoformat()
