# Local AI (student guide)

Hey Canvas uses **Local AI** so answers can stay on your computer. You do not need to know about servers, ports, or provider names to use the app day to day.

## First run

1. Launch Hey Canvas (see [DAILY-USE.md](./DAILY-USE.md)).
2. On **startup**, Hey Canvas checks your data and **Local AI** separately from Canvas.
3. Open **Settings → Local AI** to see status, installed models, tests, and comparisons.

## What you need once

1. **Local AI runtime** — on most setups this is [Ollama](https://ollama.com/download). Hey Canvas does not install it for you.
2. **At least one AI model** — install through the runtime’s app or instructions. Downloads are large; Hey Canvas never pulls models silently.

## Settings you will use

| Action | What it does |
|--------|----------------|
| **Refresh** | Re-check runtime and models |
| **Test Local AI** | Short practice prompt only (not your coursework) |
| **Select** | Choose which installed model to use (when your Hey Canvas service supports saving the choice) |
| **Run comparison** | Measure speed on synthetic tasks across models you pick |

Comparison results show **latency and success** — not a fake “quality score.” A “fastest on this comparison” note is based only on those measurements on **your** computer.

## Local only vs optional cloud

- **Local only (default)** — intelligence features expect working Local AI.
- **Optional cloud / BYO** — you can use Hey Canvas when Local AI is off if cloud is configured on your service. Canvas and Local AI problems are shown separately.

## Privacy

Benchmarks and tests use **synthetic prompts** from Hey Canvas. Your Canvas courses, assignments, grades, and materials are **not** sent into model comparisons.

## When something fails

Use **Retry**, **Local AI settings**, or the setup links in Settings. You will not see raw error dumps or file paths in the student UI.

## For maintainers (minimal backend expectations)

The UI uses these when present:

| Capability | Endpoint (expected) |
|------------|---------------------|
| Runtime status | `GET /api/assistant/status` |
| System readiness | `GET /api/readiness` (`local_runtime`, `local_model`) |
| Installed models | `GET /api/benchmarks/ollama/models` (or aliases documented in code) |
| Model comparison | `POST /api/benchmarks/ollama` with `models` + synthetic `cases` |
| Save selected model | `PUT /api/local-ai/model` `{ "model": "..." }` (optional — UI disables honestly if missing) |

No particular model is declared “best” until you run a comparison on your machine.
