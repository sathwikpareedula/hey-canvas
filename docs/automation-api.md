# Academic notifications, reminders, and calendar actions

The local automation layer is deterministic and preview-first:

- `GET /api/notifications` derives bounded notification candidates from synced
  assignments and change events, then persists read/dismiss state locally.
- `POST /api/notifications/{id}/read` and
  `POST /api/notifications/{id}/dismiss` change only local notification state.
- `GET /api/reminders/preferences` and
  `PUT /api/reminders/preferences` manage bounded local reminder preferences.
- `POST /api/reminders/preview` produces a deterministic reminder plan for a
  course assignment.
- `GET /api/calendar/links` and `POST /api/calendar/links` manage provider and
  calendar identities without storing OAuth credentials.
- `POST /api/calendar/preview` creates a persisted, stale-checkable calendar
  preview and confirmation token.
- `POST /api/calendar/confirm` validates the token, assignment identity, and
  current assignment fingerprint before executing through the injected
  provider. A confirmation is single-use.
- `POST /api/automation/preview` exposes only the explicitly allowlisted
  assistant-safe preview operations.

There are no automatic external writes. The current complete local provider is
an in-memory provider used for deterministic execution and tests. A future
OAuth-backed provider must preserve the same preview, confirmation, stale
fingerprint, and idempotency boundaries.

The in-memory provider is deterministic and idempotent for a course/assignment
event. Google Calendar remains an optional future adapter; no OAuth credentials
or tokens are stored by this backend.
