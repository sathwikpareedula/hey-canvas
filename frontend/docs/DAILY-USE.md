# Hey Canvas daily use (Windows)

## One-click launch

1. Create the Python venv at the repo root (once): `python -m venv .venv` and install backend deps per root `README.md`.
2. Install frontend deps (once): `cd frontend && npm ci`.
3. Double-click **`launcher\windows\Start-HeyCanvas.cmd`**.

Optional: run **`launcher\windows\Create-HeyCanvasShortcut.ps1`** once to add **Hey Canvas** on your Desktop.

The launcher:

- Tries to reach Local AI (Ollama) and start `ollama serve` if the command is installed (no model downloads).
- Starts the local backend if it is not already healthy on port **8000** (override with `HEY_CANVAS_BACKEND_PORT`).
- Verifies **`frontend/node_modules`** exists before starting the UI.
- Starts the Next.js dev server on port **3001** (override with `HEY_CANVAS_FRONTEND_PORT`).
- Refuses to reuse **any preexisting backend or frontend listener**, even if it appears healthy, because another checkout or version may own it. Stop that service deliberately or configure separate ports before starting. A second launch while the first is running is not an attach operation.
- Opens **`http://localhost:3001/startup`** for a student-friendly readiness screen.
- Records process IDs under **`.hey-canvas/run/`** (not committed).
- Uses a short **start lock** to reduce problems from double-clicking twice.

## Shutdown

Double-click **`launcher\windows\Stop-HeyCanvas.cmd`** or run **`Stop-HeyCanvas.ps1`**.  
Stops processes recorded in this checkout's launcher state **only when their PID and creation time match**. It does not kill arbitrary listeners on configured ports. Older PID-only state files are intentionally treated as untrusted; inspect processes manually rather than force-stopping them.

## First-run expectations

- Complete onboarding in the browser (Canvas, focus courses, local AI, privacy).
- **Local AI is default.** Hey Canvas does not silently download multi-gigabyte models.
- If Local AI or a model is missing, **Settings → Local AI** and the startup screen explain what to install manually. See [LOCAL-AI.md](./LOCAL-AI.md).

## Offline / stale data

When Canvas or the network is unavailable but synced data exists, the app shows **using synced data** and last sync time. Cached data is never presented as freshly verified from Canvas.

## Environment variables (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `HEY_CANVAS_BACKEND_PORT` | `8000` | Backend port |
| `HEY_CANVAS_FRONTEND_PORT` | `3001` | UI port |
| `HEY_CANVAS_BACKEND_HOST` | `127.0.0.1` | Backend bind URL |
| `HEY_CANVAS_FRONTEND_HOST` | `localhost` | Browser URL host |

Credentials stay in your local `.env` (never bundled by the launcher).

## Verification and troubleshooting

- [Verification](../../VERIFICATION.md) — recorded automated and local evidence, plus open limitations
- [Windows setup](../../docs/SETUP-WINDOWS.md) — fresh installation and first-run behavior
- [Troubleshooting](../../docs/TROUBLESHOOTING.md) — startup, sync, database, and model recovery

## Known external validation

- Physical microphone and speech recognition in your browser
- Real Canvas account sync on your machine
- Signed Windows installer / code signing (not required for isolated V1.2 personal evaluation)
