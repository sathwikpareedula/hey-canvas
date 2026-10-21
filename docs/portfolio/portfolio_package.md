# Hey Canvas — Portfolio Engineering Case Study

**Repository:** https://github.com/sathwikpareedula/hey-canvas  
**Focus:** Software engineering, backend systems, applied AI, and LLM application development

## Overview

Hey Canvas is a **local-first academic workspace** built with Next.js, React, TypeScript, FastAPI, SQLAlchemy, and SQLite. It integrates authorized Canvas LMS records through read-only API calls and offers optional course-aware study explanations through a locally running Ollama model.

The engineering goal is not to present a chatbot as an authoritative academic source. Instead, the system routes supported structured questions to deterministic data retrieval and uses available course materials to inform optional generative explanations.

## Architecture and responsibilities

| Layer | Stack | Responsibilities |
| --- | --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS | Academic dashboard, course views, assistant UI, streaming controls |
| API and orchestration | Python, FastAPI, Pydantic, HTTPX | Read-only Canvas integration, routing, evidence handling, cancellation |
| Persistence and documents | SQLAlchemy, SQLite, supported file parsers | Course records, metadata, bounded file preparation, provenance |
| Optional local inference | Ollama | Model-generated explanations when configured |
| Verification | pytest, Ruff, mypy, Vitest, Playwright, GitHub Actions | Unit, integration, synthetic browser, and Windows acceptance checks |

```text
Canvas LMS read-only API -> FastAPI sync -> SQLite
                                              |
                         supported document preparation
                                              |
                            course-scoped context/routing
                               /                 \
                   structured records      optional Ollama
                               \                 /
                               Next.js interface
```

## Engineering decisions worth discussing

**Reliable facts versus generated explanations.** Assignment and deadline records can be retrieved directly rather than reconstructed by an LLM. Accuracy still depends on successful synchronization and current source records.

**Course-scoped evidence.** Supported course files may be cached and text-extracted within preparation limits. File metadata alone is not searchable evidence. The system tracks source provenance and missing-evidence states.

**Streaming lifecycle.** Handling interruption requires coordinating FastAPI request cancellation, SQLAlchemy session cleanup, and downstream model streaming. Targeted regression tests cover a previously identified cancellation race.

**Local-first tradeoffs.** SQLite and optional local Ollama reduce reliance on cloud AI providers for inference, but Canvas synchronization uses network requests and optional voice/browser features can have different data flows. No absolute zero-egress or regulatory-compliance claim is made.

## Recorded verification

- **1,083 backend tests passed** and **310 frontend tests passed** at the recorded V1.2 release checkpoint.
- [GitHub Actions run #39676551978](https://github.com/sathwikpareedula/hey-canvas/actions/runs/39676551978) passed five jobs on commit `487b6fc`: history secret scan, backend, frontend, synthetic browser, and Windows synthetic acceptance.
- Gitleaks scans at that checkpoint reported no findings. This is not a guarantee that future commits or runtime configurations are free of vulnerabilities.
- Production-only npm audit reported no findings at that checkpoint; a development-only transitive `braces` advisory remained documented.
- The latest complete real-Ollama 22-scenario evaluation recorded **16/22 passes**. This is a bounded test result, not a general model-accuracy score.

Refer to [VERIFICATION.md](../../VERIFICATION.md) for the limitations and original evidence. Metrics must not be presented as results of later commits unless rerun.

## Public screenshots

The six curated screenshots are in [portfolio-assets/hey-canvas](../../portfolio-assets/hey-canvas/). They depict **synthetic demonstration data**, not private student records or live model-evaluation evidence.

| Asset | Shows |
| --- | --- |
| `01-dashboard-desktop.png` | Academic dashboard and course overview |
| `02-ai-study-assistant.png` | **Prewritten synthetic** two-link forward-kinematics explanation with sample course references |
| `03-today-priorities.png` | Daily priorities and assignments |
| `04-deadline-calendar.png` | Calendar view |
| `05-course-materials.png` | Supported course materials and preparation status |
| `06-mobile-view.png` | Responsive interface |

The assistant screenshot must **not** be captioned as a real Ollama-generated response, verified professor advice, or evidence of live retrieval accuracy.

## Security, licensing, and status

Canvas access is intended to be read-only. API tokens, student data, local databases, and downloaded course files should never be committed or used in public screenshots. The project is [MIT licensed](../../LICENSE); third-party Canvas/course materials are not relicensed by that MIT grant.

**Status:** Public source code for a locally tested V1.2 release candidate; no public hosted production service. Independent project, not endorsed by Instructure or a university. Known limits include incomplete supported-file coverage, browser-local conversation storage, unverified physical microphone capture, and bounded real-model reliability.

For a deeper technical narrative, read [PROJECT_STORY.md](../../PROJECT_STORY.md).
