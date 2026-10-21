# Windows setup — Hey Canvas V1.2

This guide is for a **fresh checkout**, not an upgrade of an existing student database. Hey Canvas is a local-first development candidate, not a hosted service. Use a supported Windows PowerShell terminal. The repository may be private; cloning requires access.

## Prerequisites

- Python 3.12 or newer and Git.
- Node.js/npm compatible with the lockfile. **Node 22.13+ (prefer a current supported LTS release)** avoids a known engine warning from a development dependency; Node 22.11 produced a warning during October 2026 acceptance.
- Ollama is optional for academic records, but required for local generated explanations. Install a compatible model explicitly; model downloads are not automatic.

## Fresh installation

In PowerShell:

```powershell
git clone https://github.com/sathwikpareedula/hey-canvas.git
cd hey-canvas
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd frontend
npm ci
cd ..
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip check
cd frontend
npm run typecheck
cd ..
```

**Important:** this repository contains the verified V1.2 release snapshot on the default `main` branch. Do not switch branches inside an existing installation that contains local student data.

The local `.env` is ignored by Git. The example includes a **blank** `CANVAS_TOKEN` and a UTA-specific example `CANVAS_BASE_URL`; students at other institutions must supply their own authorized Canvas URL. Never paste credentials into a GitHub issue, screenshot, or public log. Consult the app's connection settings for credential setup; no real Canvas account is needed to inspect source code or run synthetic tests.

To use local AI, install Ollama and pull a supported model, for example:

```powershell
ollama pull llama3.2:3b
ollama list
```

Model downloads may be large and require an internet connection. Local CPU generation can be slow. Configure the selected installed model under **Settings → Local AI**; do not assume it is ready solely because Ollama is installed.

## Start and stop

From the repository root:

```powershell
.\launcher\windows\Start-HeyCanvas.cmd
```

The launcher starts local services, usually backend `http://127.0.0.1:8000` and frontend `http://localhost:3001/startup`. It refuses to adopt listeners from other checkouts. If ports are occupied, stop the known owner first or use documented port overrides; never terminate unrelated processes blindly.

To stop:

```powershell
.\launcher\windows\Stop-HeyCanvas.cmd
```

The first-run startup screen distinguishes backend, database, Canvas connection, and local AI. A healthy database does **not** mean Canvas credentials are configured or that a synchronization completed. Do not interpret an empty dashboard as lost data without first checking the selected database and sync history.

## Using Canvas

Configure an authorized, read-only Canvas API connection in the local installation. Canvas sync contacts your Canvas institution over the network; it is **not** an offline operation. Start the first sync intentionally from the app, then review Sync History for status and any errors. Existing records may be stale if a later sync fails.

## Safe data handling

Do not copy real databases between checkouts or change `DATABASE_URL` casually. Back up SQLite data while services are stopped and verify source/destination schema before any migration. A new clone starts without your prior local academic records, which is expected.

For everyday use, see [Daily use](../frontend/docs/DAILY-USE.md). For errors, see [Troubleshooting](TROUBLESHOOTING.md). For test claims and limitations, see [Verification](../VERIFICATION.md).
