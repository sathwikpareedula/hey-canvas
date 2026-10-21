# Engineering Hey Canvas

**Full-stack software engineering, academic data integration, and reliability-focused AI application development.**

## Problem

Course information is fragmented across assignments, announcements, calendars, and documents. Generic AI assistants do not inherently know which course a question concerns or whether a claimed deadline is supported by an actual record.

Hey Canvas explores how a local-first workspace can combine structured academic data with course-aware study assistance.

## What I built

The Next.js/React interface provides courses, upcoming work, materials, and an academic assistant. A Python/FastAPI backend reads authorized Canvas LMS data, normalizes supported records in SQLite, and prepares supported document text for course-scoped retrieval.

The assistant distinguishes two paths:

- **Structured academic questions:** deterministic retrieval from available records, avoiding unnecessary model inference.
- **Explanatory study questions:** optional local Ollama generation using available course context and source evidence.

Neither path guarantees completeness or correctness. Missing or unprepared evidence is not treated as proof that an item does not exist.

## Architecture

```text
Authorized Canvas LMS (read-only API)
                |
      Guarded synchronization
                |
       FastAPI + SQLAlchemy
                |
       SQLite course records ---- Supported file cache
                |                         |
     Structured fact retrieval    Text extraction and provenance
                \                         /
                 Course-scoped context
                          |
                  Academic intent routing
                   /                 \
       Deterministic responses    Optional Ollama
                   \                 /
                Source-aware UI
              Next.js / React
```

**Technologies:** Python, FastAPI, Pydantic, HTTPX, SQLAlchemy, SQLite, Next.js, React, TypeScript, Tailwind CSS, optional Ollama, pytest, Ruff, mypy, Vitest, Playwright, and GitHub Actions.

## Engineering challenges

### Distinguishing file metadata from searchable evidence

Canvas file listings do not imply the corresponding documents have been downloaded, extracted, or indexed. Hey Canvas tracks supported document preparation and provenance, processes content within bounded limits, and exposes unavailable-evidence states.

### Preventing cross-course confusion

Course selection scopes relevant retrieval. Academic source text is treated as untrusted data, not as a new instruction to the assistant. Tests cover misleading instructions and incorrect course context; these safeguards do not establish immunity to all prompt-injection attempts.

### Streaming and cancellation

Streaming involves request setup, database access, model response delivery, and cleanup. Development uncovered a SQLAlchemy session-lifecycle race during cancellation. The application coordinates setup and teardown and includes targeted regression tests for cancellation behavior.

### Testing model behavior separately from app behavior

Deterministic synthetic responses are useful for repeatable UI and integration tests, but they are **not** evidence that a live language model generated the displayed text. The public robotics screenshot is a prewritten synthetic demo. Ollama-backed generation is an optional, separate local mode.

## Verification and limitations

At the recorded V1.2 release checkpoint, the project reported **1,083 backend tests passing** and **310 frontend tests passing**. The [five-job GitHub Actions run](https://github.com/sathwikpareedula/hey-canvas/actions/runs/39676551978) passed on commit `487b6fc`, including history-secret scanning, frontend/backend tests, synthetic browser journeys, and Windows synthetic acceptance. These results describe that tested revision; consult current Actions runs for later changes.

The most recent complete 22-scenario real-Ollama evaluation recorded **16 passes out of 22**. It does not establish universal model accuracy or responsiveness. Browser microphone capture, live Canvas authorization on a fresh installation, and every third-party course-file format were not fully covered by the recorded clean-install acceptance. Some frontend integration-marked tests were skipped. See [VERIFICATION.md](VERIFICATION.md) for detailed scope and caveats.

Data is stored locally by default, but **Canvas sync necessarily communicates with Canvas**. Optional browser voice features and external services have their own privacy considerations. Do not describe the project as zero-egress, FERPA-certified, or production-secure.

## Outcome

Hey Canvas demonstrates how I design a full-stack AI application: dependable data integration, explicit boundaries between facts and inference, course-scoped retrieval, cancellable asynchronous operations, and tests that distinguish a convincing demo from real-model reliability.

**Status:** Public V1.2 source snapshot and locally tested release candidate; not a hosted production service. Independent student-built project, not affiliated with or endorsed by Instructure or a university. Public screenshots use synthetic data. The application does not submit assignments or modify Canvas course data.
