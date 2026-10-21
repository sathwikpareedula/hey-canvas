"""100+ distinct synthetic-student acceptance campaign (model-independent, deterministic)."""

from __future__ import annotations

import pytest

from tests.acceptance.conftest import CAMPAIGN_RESULTS
from tests.acceptance.harness import student_world
from tests.acceptance.scenarios import SCENARIOS, Recorder
from tests.acceptance.student_factory import build_student

PRIMARY_SEED = 20261015
SECONDARY_SEEDS = (7, 424242)
PRIMARY_STUDENTS = 100
SECONDARY_STUDENTS = 40

CASES = [(PRIMARY_SEED, i) for i in range(PRIMARY_STUDENTS)] + [
    (seed, i) for seed in SECONDARY_SEEDS for i in range(SECONDARY_STUDENTS)
]


def test_profiles_are_distinct_and_reproducible() -> None:
    first = [build_student(PRIMARY_SEED, i) for i in range(PRIMARY_STUDENTS)]
    second = [build_student(PRIMARY_SEED, i) for i in range(PRIMARY_STUDENTS)]
    assert first == second
    signatures = {
        (
            p.tz_name,
            p.now,
            p.sync_state,
            tuple(
                (
                    c.name,
                    c.enrollment_state,
                    tuple((a.name, a.due_at, a.points) for a in c.assignments),
                )
                for c in p.courses
            ),
        )
        for p in first
    }
    assert len(signatures) == PRIMARY_STUDENTS
    assert len({p.tz_name for p in first}) >= 5
    assert {len(p.courses) for p in first} >= {1, 2, 3, 4, 5}
    assert any(len({c.code for c in p.courses}) < len(p.courses) for p in first), (
        "campaign must include overlapping course codes"
    )
    assert {c.enrollment_state for p in first for c in p.courses} >= {
        "active",
        "completed",
        "invited",
    }
    assert {p.sync_state for p in first} == {"fresh", "stale", "failed", "partial", "never"}


@pytest.mark.parametrize(
    ("seed", "index"), CASES, ids=[f"seed{s}-student{i:03d}" for s, i in CASES]
)
def test_student_journeys(seed: int, index: int) -> None:
    profile = build_student(seed, index)
    recorder = Recorder()
    with student_world(profile) as world:
        for scenario in SCENARIOS:
            scenario(world, recorder)
    for feature, case, passed, detail in recorder.cases:
        CAMPAIGN_RESULTS.append(
            {
                "student": profile.label,
                "feature": feature,
                "case": case,
                "passed": passed,
                "detail": detail,
            }
        )
    failures = recorder.failures
    assert not failures, "\n".join(f"[{f[0]}] {f[1]} :: {f[3]}" for f in failures)
