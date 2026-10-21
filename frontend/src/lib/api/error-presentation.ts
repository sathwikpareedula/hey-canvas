import {
  AcademicApiErrorKind,
  AcademicApiNotImplementedError,
  toAcademicApiError,
} from "@/lib/api/errors";

export interface PresentedApiError {
  kind: AcademicApiErrorKind;
  title: string;
  message: string;
  retryable: boolean;
}

const ACTIONABLE_PREFIXES = [
  "choose a course",
  "select a course",
  "no saved study session",
  "no study session",
  "study session not found",
];

function isActionableUserMessage(message: string): boolean {
  const lower = message.toLowerCase();
  return ACTIONABLE_PREFIXES.some((p) => lower.includes(p));
}

export function presentAcademicError(error: unknown): PresentedApiError {
  const err = toAcademicApiError(error);

  if (err instanceof AcademicApiNotImplementedError) {
    return {
      kind: "not_implemented",
      title: "Not available yet",
      message:
        "This capability is not wired to the backend in HTTP mode yet. Switch to mock mode for development UI, or wait for the next backend milestone.",
      retryable: false,
    };
  }

  switch (err.kind) {
    case "network":
      return {
        kind: err.kind,
        title: "Connection problem",
        message:
          "Hey Canvas could not reach your local service. Use the Windows launcher or wait a moment and retry.",
        retryable: true,
      };
    case "not_found":
      return {
        kind: err.kind,
        title: err.message.toLowerCase().includes("session") ? "No saved session" : "Not found",
        message:
          err.message.toLowerCase().includes("session")
            ? "Start a new study session or pick a course from the list below."
            : "The requested academic item is not available in the local database.",
        retryable: false,
      };
    case "parse":
    case "malformed":
      return {
        kind: err.kind,
        title: "Unexpected response",
        message:
          "The backend returned data in an unexpected shape. No mock data was substituted.",
        retryable: true,
      };
    case "http": {
      const lower = err.message.toLowerCase();
      if (err.status === 401 || (lower.includes("canvas") && lower.includes("token"))) {
        return {
          kind: err.kind,
          title: "Canvas connection needs attention",
          message:
            "Your local service could not authorize Canvas access. Update the token on your computer (not in this browser), sync again, then retry.",
          retryable: true,
        };
      }
      return {
        kind: err.kind,
        title: "Request failed",
        message: `The academic API rejected the request (${err.status ?? "error"}).`,
        retryable: err.status !== 404 && err.status !== 422,
      };
    }
    case "not_implemented":
      return {
        kind: "not_implemented",
        title: "Not available yet",
        message: err.message,
        retryable: false,
      };
    default:
      if (isActionableUserMessage(err.message)) {
        return {
          kind: "unknown",
          title: "Action needed",
          message: err.message,
          retryable: false,
        };
      }
      return {
        kind: "unknown",
        title: "Something went wrong",
        message:
          err.message && err.message !== "An unexpected error occurred"
            ? err.message
            : "An unexpected error occurred while loading academic data.",
        retryable: true,
      };
  }
}
