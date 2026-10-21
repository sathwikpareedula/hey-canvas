# Hey Canvas (frontend)

Next.js + TypeScript UI for **Hey Canvas**. The browser talks only to the local FastAPI backend. It never calls Canvas directly and never stores Canvas credentials.

Product UX (onboarding, focus courses, local AI, privacy, demo mode): see [docs/PRODUCT.md](./docs/PRODUCT.md).

Daily Windows launch, shutdown, and offline behavior: see [docs/DAILY-USE.md](./docs/DAILY-USE.md).

Local AI setup, models, and benchmarking: see [docs/LOCAL-AI.md](./docs/LOCAL-AI.md).

## Requirements

- Node.js 22.13+ (or another compatible supported LTS release)
- npm
- The local FastAPI backend for interactive use

## Install

```bash
cd frontend
npm ci
```

## Development

For normal development, start the backend first, then run:

```bash
npm run dev
```

The frontend proxies `/api/*` to the backend configured by `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000`; see `next.config.ts`). To choose it explicitly in Windows PowerShell:

```bash
$env:NEXT_PUBLIC_ACADEMIC_API_MODE = "http"
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Direct `npm run dev` uses Next.js's default port 3000. The supported Windows launcher starts the UI on port 3001 and waits for `/startup` before opening it. Use **`localhost`**, not `127.0.0.1`, for the frontend origin.

For an isolated synthetic catalog with no Canvas credentials or Ollama model, finish the root installation and run `launcher\windows\Start-HeyCanvas-Demo.cmd`. The demo launcher uses a dedicated database under the ignored `.hey-canvas` runtime directory and never seeds the personal database.

When the backend serves **synthetic/demo** courses or the assistant provider is `synthetic`, the top bar shows a **Demo data** badge. Real Canvas sync data hides the badge automatically.

| Area | Route |
|------|--------|
| Hey Canvas | `/` |
| Dashboard | `/dashboard` |
| Courses / Assignments / Materials | `/courses`, `/assignments`, `/materials` |
| Study / Practice / Guide | `/study`, `/study/guide` |
| Notifications | `/notifications` |
| Settings (reminders) | `/settings` |

App-wide **Ctrl+K** command palette.

## Voice (V1.1)

Push-to-talk and optional in-tab **"Hey Canvas"** hands-free mode when the browser supports **Web Speech API** (best on Chromium desktop). See [docs/VOICE-OPERATING-BOUNDARY.md](./docs/VOICE-OPERATING-BOUNDARY.md) for the exact operating boundary (not OS-level wake).

- Tap the **microphone** to start; tap again to stop. Edit the transcript before **Send**.
- **Settings → Voice**: enable hands-free wake phrase; recognition pauses during spoken responses.
- Optional **spoken responses** (speaker toggle): concise summaries only — no IDs, URLs, tokens, or JSON.
- Microphone permission is required. Browser speech recognition behavior and any provider processing depend on the browser and platform; do not assume all voice processing is offline.

Calendar actions from chat or voice still require **Review and confirm** in the calendar dialog; voice is never treated as confirmation.

## Testing

```bash
npm run test          # unit tests (Vitest)
npm run typecheck
npm run lint
npm run build
```

Optional integration smoke (backend must be running, read-only):

```bash
set VITEST_INCLUDE_INTEGRATION=1
set RUN_PRODUCT_INTEGRATION=1
set RUN_ASSISTANT_INTEGRATION=1
npm run test
```

Physical microphone is **not** required for CI; speech APIs are mocked in tests.

## Security & privacy

- No Canvas tokens or passwords in the UI or `localStorage`.
- `localStorage` stores UI preferences, opaque study/practice session identifiers, and bounded browser conversation history. This is not durable backend message persistence; avoid storing sensitive text in demo conversations.
- Service worker caches shell assets only; **`/api` responses are not cached** (`public/sw.js`).
- Academic content is rendered as plain text (no arbitrary HTML).

## Scripts

| Command | Description |
|--------|-------------|
| `npm run dev` | Dev server |
| `npm run dev:http` | Explicit dev server on port 3000 |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | ESLint |
| `npm run test` | Vitest |
| `npm run typecheck` | `tsc --noEmit` |
