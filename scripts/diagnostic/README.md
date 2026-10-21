# Diagnostic scripts (not production)

One-off verification helpers for local machine runs. Output goes to `.hey-canvas/diagnostic/` (gitignored).

- `ollama_benchmark.py` — synthetic Ollama measurements when product `POST /api/benchmarks/ollama` is unavailable in this worktree backend. Warms each model and unloads between models; writes incremental JSON under `.hey-canvas/diagnostic/`.
- `ollama_latency_tune.py` — before/after latency comparison for inference options (measurement only).
- `launcher-acceptance.ps1` — executable Windows launcher checks (isolated ports).
- `ollama_http_probe.ps1` — bounded `GET /api/tags` readiness (never unbounded `ollama list`).
- `student_red_team_runtime.py` — bounded prompt battery against an explicitly selected local test stack.
- `double-click-start.ps1` — simulates double `Start-HeyCanvas.cmd` on isolated ports.
- `publication-scan.ps1` — bounded secret-pattern scan of **tracked** files.
- `ollama_repeat_measure.py` — repeat latency samples for top candidates after warm-up.

Latest full diagnostic on this machine (2026-10-03): see `.hey-canvas/diagnostic/ollama-benchmark-20261003T110630Z.json`. Practical default candidate from measurements: **qwen3:4b-instruct** (7/7 tasks, lowest warm total among full passes); fastest TTFT among passes: **qwen3.5:2b**. Historical diagnostic results are not a guarantee of current model performance or shipped defaults.
