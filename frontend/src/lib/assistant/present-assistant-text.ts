const DEV_CONTEXT_LINE =
  /course context:\s*(unresolved|ambiguous|synthetic-[\w-]+|[a-z]+-\d+)/i;

const SYNTHETIC_ECHO =
  /^i can help with:\s*.+?\.\s*course context:/i;

const INTERNAL_FRAMING =
  /\b(canvas_truth|system policy|application rules|provider contract|developer instructions|CANVAS_TRUTH)\b/i;

/** Hide low-value synthetic fallback lines; keep real errors and substantive text. */
export function shouldHideAssistantTextBlock(content: string | undefined): boolean {
  if (!content?.trim()) return true;
  const text = content.trim();
  if (DEV_CONTEXT_LINE.test(text) && text.length < 220) return true;
  if (SYNTHETIC_ECHO.test(text)) return true;
  return false;
}

export function sanitizeAssistantTextContent(content: string | undefined): string | undefined {
  if (!content?.trim()) return undefined;
  if (INTERNAL_FRAMING.test(content)) return undefined;
  if (shouldHideAssistantTextBlock(content)) return undefined;
  return content.trim();
}

export function deadlineEmptyMessageFromHint(hint?: string): string {
  const h = (hint ?? "").toLowerCase();
  if (h.includes("tomorrow")) return "Nothing due tomorrow.";
  if (h.includes("today")) return "Nothing due today.";
  if (h.includes("next")) return "Nothing due next week.";
  if (h.includes("this")) return "Nothing due this week.";
  if (h.includes("overdue") || h.includes("past due")) return "No overdue assignments.";
  if (h.includes("week")) return "Nothing due this week.";
  return "No deadlines in this range.";
}
