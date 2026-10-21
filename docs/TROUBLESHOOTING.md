# Troubleshooting — Hey Canvas

This guide favors **read-only diagnosis first**. Do not delete local databases, remove project folders, expose API tokens, or run a blind Git reset to fix startup issues.

## Startup says Canvas is not ready

The backend, SQLite database, Canvas credentials, and Ollama are independent readiness checks. A working dashboard can show previously synchronized records even if Canvas is currently disconnected. Confirm that you configured an authorized Canvas connection in this checkout and inspect **Sync History**. Do not assume the `Refresh history` action starts a new sync; use the explicitly labeled sync action when ready.

If the UI reports **Could not start sync**, that is a generic error, not proof that the backend is stopped. Confirm backend health, inspect local logs carefully, and check connection configuration. Avoid posting full logs or environment files because they may contain private academic data.

## Wrong or older interface appears

Different checkouts can use the same localhost ports. Verify the folder and commit:

```powershell
git rev-parse HEAD
git branch --show-current
git status --short
```

The current launcher refuses to adopt unrelated listeners. Stop the known older checkout using its own `Stop-HeyCanvas.cmd` before launching the intended one. Do not run `git pull` or switch branches blindly when working with local databases.

## Empty courses after cloning

Git does not include your personal SQLite database or Canvas token. An empty database in a fresh clone is normal. It is not evidence that an older database was deleted. Before any data transfer, stop services, preserve backups, verify paths and schema, and obtain explicit authorization for changes.

## Python or frontend dependencies missing

From the repo root:

```powershell
.\.venv\Scripts\python.exe -m pip check
cd frontend
npm run typecheck
cd ..
```

If `.venv` or `frontend/node_modules` is absent, follow [Windows setup](SETUP-WINDOWS.md). Use `npm ci` with the committed lockfile. An `EBADENGINE` warning indicates a dependency's Node version requirement is unmet; use a compatible supported Node release.

## AI is slow, generic, or times out

Local model speed depends on hardware, model size, and available evidence. Some academic facts use deterministic data paths; generated explanations may take longer and can be incomplete. Verify deadlines in the original Canvas records. When the assistant cannot find an assignment description, it must not invent instructor requirements. Missing searchable document text and PDFs needing OCR can reduce evidence quality. Check **Settings → Local AI**, model availability, and Materials preparation status.

## Logs and privacy

Launcher logs are stored under `.hey-canvas/run/logs/` and are ignored by Git. Read them locally, redact credentials and private course information before sharing, and never commit logs or personal academic files.

## Stop safely

Run `launcher\windows\Stop-HeyCanvas.cmd` from the corresponding checkout. It uses recorded process identity checks; it does not indiscriminately kill every process using ports 8000 or 3001.

For measured verification results and known gaps, see [VERIFICATION.md](../VERIFICATION.md).
