# Structured study workflows

The backend exposes bounded, typed workflows rather than another conversation
store:

- `POST /api/study-sessions` creates a durable plan using course, goal,
  duration, topics, mode, assignments, and attributable evidence references.
- `POST /api/study-sessions/{id}/progress` records ordered-step progress.
- `POST /api/study-sessions/{id}/continue` resumes durable study continuity.
- `POST /api/study-sessions/practice` creates an application-owned practice
  session. Questions are marked as generated unless a future provider supplies
  attributable evidence.
- `POST /api/study-sessions/practice/{id}/answer` records an answer and typed
  feedback; `.../hint` returns a bounded hint.
- `POST /api/study-guides` returns a structured guide with concepts,
  explanations, checklists, prompts, evidence references, and explicit
  uncertainty when professor evidence is missing.

Study modes are limited to `learn`, `review`, `practice`, and `exam_prep`.
These workflows never call Canvas quizzes, submit answers, or let generated
content change Canvas truth. The assistant operation boundary uses the typed
`study_plan`, `practice_session`, and `study_guide` operations; arbitrary tool
names are not accepted.
