# Public / portfolio demo guidance

## Use synthetic data only

- Run frontend in **mock mode** or backend **synthetic** provider for screenshots and recordings.
- Confirm the **Demo data** badge is visible when synthetic catalog is active.

## Do not publish

- Real assignment titles, professor names, or student identifiers
- Real grades, submissions, or Canvas IDs tied to people
- `.env`, tokens, `data/` SQLite, downloaded PDFs, logs under `.hey-canvas/`
- Screenshots that include file paths, URLs with tokens, or network tab credentials

## Recommended screenshot flows (synthetic)

1. Dashboard / Today with demo courses  
2. Hey Canvas chat with course badge  
3. Settings → Local AI (status + benchmark table with demo/mock)  
4. Settings → Voice (hands-free toggle)  
5. Startup readiness checklist  

## Before `git push` (human checklist)

- [ ] `git status` — no `.env`, `data/*`, `.hey-canvas/`
- [ ] No hardcoded personal paths in committed files
- [ ] README claims match implemented behavior
- [ ] Wake-word limitation documented (browser-based)
