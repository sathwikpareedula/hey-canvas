export type AcademicApiErrorKind =
  | "network"
  | "not_implemented"
  | "not_found"
  | "http"
  | "parse"
  | "malformed"
  | "unknown";

export class AcademicApiError extends Error {
  readonly kind: AcademicApiErrorKind;

  constructor(
    message: string,
    readonly status?: number,
    code?: string,
  ) {
    super(message);
    this.name = "AcademicApiError";
    this.kind = classifyCode(code, status);
  }
}

export class AcademicApiNotImplementedError extends AcademicApiError {
  constructor(feature: string) {
    super(`${feature} is not available in HTTP API mode yet`, undefined, "not_implemented");
    this.name = "AcademicApiNotImplementedError";
  }
}

export class AcademicApiNotFoundError extends AcademicApiError {
  constructor(resource: string) {
    super(`${resource} was not found`, 404, "not_found");
    this.name = "AcademicApiNotFoundError";
  }
}

export class AcademicApiMalformedError extends AcademicApiError {
  constructor(detail: string) {
    super(detail, undefined, "malformed");
    this.name = "AcademicApiMalformedError";
  }
}

function classifyCode(code?: string, status?: number): AcademicApiErrorKind {
  if (code === "network") return "network";
  if (code === "not_implemented") return "not_implemented";
  if (code === "not_found" || status === 404) return "not_found";
  if (code === "parse") return "parse";
  if (code === "malformed") return "malformed";
  if (code === "http") return "http";
  return "unknown";
}

export function toAcademicApiError(error: unknown): AcademicApiError {
  if (error instanceof AcademicApiError) return error;
  if (error instanceof Error) {
    const lower = error.message.toLowerCase();
    if (
      lower === "network error" ||
      lower.includes("failed to fetch") ||
      lower.includes("load failed")
    ) {
      return new AcademicApiError(error.message, undefined, "network");
    }
    return new AcademicApiError(error.message, undefined, "unknown");
  }
  return new AcademicApiError("An unexpected error occurred", undefined, "unknown");
}
