import type { DocumentIngestionState } from "@/lib/domain/types";

export interface DocumentUserStatus {
  label: string;
  tone: "muted" | "warn" | "danger" | "ok";
  description: string;
}

export function documentUserStatus(options: {
  ingestionState?: DocumentIngestionState;
  backendStatus?: string;
  needsOcr?: boolean;
  isStale?: boolean;
}): DocumentUserStatus | null {
  const { ingestionState, backendStatus, needsOcr, isStale } = options;
  if (backendStatus === "failed" || ingestionState === "failed") {
    return {
      label: "Could not prepare",
      tone: "danger",
      description: "This file could not be processed. Try sync again or open it from Canvas.",
    };
  }
  if (backendStatus === "retry" || backendStatus === "retrying") {
    return {
      label: "Retrying",
      tone: "warn",
      description: "Hey Canvas is trying to prepare this material again.",
    };
  }
  if (backendStatus === "unsupported") {
    return {
      label: "Unsupported format",
      tone: "danger",
      description: "Hey Canvas cannot read this file type yet.",
    };
  }
  if (needsOcr || backendStatus === "needs_ocr") {
    return {
      label: "Needs text recognition",
      tone: "warn",
      description:
        "This file has no searchable text on your computer yet. Grounded search and chat cannot read it until optional OCR is configured.",
    };
  }
  if (backendStatus === "downloading" || backendStatus === "preparing") {
    return {
      label: "Preparing",
      tone: "muted",
      description: "Downloading or preparing this material locally.",
    };
  }
  if (backendStatus === "parsing" || ingestionState === "pending") {
    return {
      label: "Indexing",
      tone: "muted",
      description: "Parsing content so you can ask questions.",
    };
  }
  if (isStale || backendStatus === "stale") {
    return {
      label: "Updated on Canvas",
      tone: "warn",
      description: "A newer version may exist — sync again for the latest copy.",
    };
  }
  if (ingestionState === "searchable" || backendStatus === "ready" || backendStatus === "indexed") {
    return {
      label: "Ready",
      tone: "ok",
      description: "You can ask questions about this material.",
    };
  }
  if (backendStatus === "metadata_only" || backendStatus === "not_ingested") {
    return {
      label: "Details only",
      tone: "muted",
      description: "Metadata is available; full text is not indexed yet.",
    };
  }
  return null;
}
