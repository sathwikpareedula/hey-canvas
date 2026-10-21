# Local academic assistant API

This branch exposes a provider-neutral assistant interface above the deterministic academic tool layer. The backend does not require a live model; it defaults to a local synthetic provider for unit tests and local offline development.

## Provider configuration

The local runtime is configured with environment variables:

- `ACADEMIC_MODEL_PROVIDER` — `synthetic` (default) or `ollama`
- `OLLAMA_BASE_URL` — loopback-only default `http://127.0.0.1:11434`
- `OLLAMA_MODEL` — model name to use, for example `llama3.2`
- `ASSISTANT_REQUEST_TIMEOUT_SECONDS` — HTTP timeout in seconds

Non-loopback Ollama hosts are rejected by the client adapter.

## Endpoints

### POST /api/assistant/respond

Returns a final `AssistantResponse` as JSON.

Request body:

```json
{
  "query": "What do I have due today?",
  "course_id": "9007199254740993",
  "study_mode": "review",
  "session_id": "session-123",
  "operation": "answer"
}
```

Response body:

```json
{
  "status": "ok",
  "course_id": "9007199254740993",
  "blocks": [
    {
      "type": "text",
      "text": "You have one assignment due today.",
      "references": []
    }
  ]
}
```

### POST /api/assistant/stream

Returns a server-sent event stream with `text/event-stream` media type.

Event payloads are shaped like:

```json
{
  "type": "text_delta",
  "session_id": "session-123",
  "course_id": "9007199254740993",
  "text": "You have one assignment due today."
}
```

Supported event types:

- `started`
- `text_delta`
- `block`
- `source`
- `warning`
- `error`
- `follow_up`
- `completed`

`AssistantRequest.active_course_id` may be supplied by the host UI when the
user is operating inside an active course. An explicit `course_id` takes
precedence over that active context; neither value is inferred by the model.

Deterministic workflow requests also add structured blocks without requiring
the frontend to parse prose: `study_plan`, `practice_question`,
`practice_feedback`, `study_guide`, `notification_summary`,
`reminder_preview`, `calendar_action_preview`, and
`calendar_action_result`. Calendar requests remain preview-only until the
separate confirmation endpoint validates the single-use token.

The `deadline_group` payload is:

```json
{
  "window": "tomorrow",
  "assignments": [],
  "empty": true,
  "message": "Nothing due tomorrow."
}
```

An empty result is valid data, not an error. A `study_plan` block contains the
typed `StudySessionView` payload, including `session_id`, `course_id`, `goal`,
`duration_minutes`, `topics`, `study_mode`, `assignment_ids`, `steps`, and
`progress`.

## Error model

The API distinguishes the following safe categories:

- `bad request` — invalid fields or unsupported operation
- `ambiguous course` — router could not resolve a unique course
- `missing entity` — assignment or course not found
- `provider unavailable` — local model host is unreachable or misconfigured
- `provider timeout` — provider exceeded the timeout limit
- `provider malformed output` — returned invalid data
- `internal deterministic-tool failure` — backend local service failed
- `cancelled request` — client disconnected before completion

These are returned as HTTP 400, 404, 503, or as SSE `error` events.

## Study mode values

- `learn`
- `review`
- `practice`
- `exam_prep`

## Authority and evidence

The assistant API preserves the backend authority model:

- `canvas_truth`
- `professor_material`
- `user_profile`
- `user_study_context`
- `routing_evidence`
- `change_event`

Document excerpts are presented as evidence data only. They are not treated as instructions and cannot redefine safety policy or course identity.

## Cancellation behavior

Clients disconnecting from the streaming endpoint cancel subsequent event forwarding. The request is not kept alive as a background daemon.
