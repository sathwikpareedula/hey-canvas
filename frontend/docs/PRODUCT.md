# Hey Canvas product experience

Hey Canvas is a course-aware academic workspace. It can answer questions using authorized Canvas records and successfully prepared materials; coverage depends on synchronization and document preparation.

## Daily startup

Open Hey Canvas from your installed app or local dev URL. You should not need a daily terminal ritual. If the local academic service is offline, the app shows actionable guidance instead of raw connection errors.

## First-run onboarding

1. Welcome  
2. Canvas (read-only)  
3. Sync  
4. Focus courses  
5. Local AI  
6. Privacy  
7. Ready  

Resume anytime from **Settings → Run setup wizard again**.

## Focus courses

Choose the courses you care about this term. They appear under **My courses** in the sidebar. **All courses** lists the full synced catalog. Focus courses can change each semester without deleting history.

## Course workspaces

Each focus course opens a workspace with overview, assignments, materials, and study shortcuts. Course-scoped Hey Canvas keeps context obvious without repeating giant titles.

## General vs course-scoped chat

Hey Canvas shows **All courses** or a course badge. Cross-course questions (due today, changes, workload) work in general mode. Course-specific study stays scoped.

## Free local AI

The default application design is local-first; Canvas synchronization and optional services still involve network communication. Optional cloud / BYO provider is explicit opt-in in Settings. The UI does not store ChatGPT passwords.

## Demo mode

When the backend serves synthetic data, a **Demo data** badge appears. Demo never mixes with real local Canvas data in the UI messaging.

## Server-backed product API (adapter contract)

The frontend uses typed clients under `lib/api/product-settings-api.ts`. Backend integration endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| GET/PUT | `/api/product/settings` | Focus courses, AI mode, model tier |
| GET/PUT | `/api/product/course-policies/{courseId}` | Per-course AI policy notes |
| GET | `/api/product/readiness` | Startup/readiness checks |
| GET/PUT | `/api/product/workspaces/{courseId}` | Course workspace metadata |
| POST | `/api/product/disambiguation/resolve` | Assignment/material/course candidates |
| POST | `/api/product/data/lifecycle` | Confirmed data lifecycle actions |

Until endpoints exist, the service keeps a **local cache** and one-time migration from existing browser preferences without wiping user data.

## Known limitations

- Canvas connection and sync are configured on the computer running the local backend (not in-browser tokens).
- Model install/download is controlled by your local AI runtime — Hey Canvas does not silently download multi-GB models.
- Integration tests require `VITEST_INCLUDE_INTEGRATION=1` and a running backend.
