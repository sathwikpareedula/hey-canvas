import type { Assignment, ChatMessage } from "@/lib/domain/types";

const FOLLOW_UP_PATTERNS =
  /\b(when is it due|when's it due|what files|what material|professor (said|give)|individual report|that (one|assignment)|the assignment|how do i (do|complete)|explain it|quiz me|harder|instructions did)\b/i;

const ASSIGNMENT_HINT_PATTERNS =
  /\b(report|homework|assignment|quiz|exam|project|lab|worksheet|charter|sprint)\b/i;

export function isFollowUpEntityPrompt(text: string): boolean {
  const q = text.trim().toLowerCase();
  if (!q) return false;
  if (FOLLOW_UP_PATTERNS.test(q)) return true;
  if (q.length < 48 && ASSIGNMENT_HINT_PATTERNS.test(q) && !/\bdue (today|tomorrow|next week|this week)\b/.test(q)) {
    return true;
  }
  return false;
}

/** Best-effort assignment id from recent assistant deadline/practice blocks or user mentions. */
export function activeAssignmentIdFromMessages(messages: ChatMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    if (!msg || msg.role !== "assistant") continue;
    for (const block of msg.blocks ?? []) {
      if (
        (block.type === "deadlines" || block.type === "assignment_summary")
        && "assignments" in block
        && block.assignments?.length === 1
      ) {
        return block.assignments[0]!.id;
      }
    }
  }
  return null;
}

export function activeDocumentIdFromMessages(messages: ChatMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    if (!msg || msg.role !== "assistant") continue;
    for (const block of msg.blocks ?? []) {
      if (block.type !== "document_answer" || !block.sources?.length) continue;
      const ids = new Set(
        block.sources
          .map((source) => source.provenance.documentId)
          .filter((id): id is string => Boolean(id)),
      );
      if (ids.size === 1) return [...ids][0]!;
    }
  }
  return null;
}

export function matchAssignmentsInText(text: string, assignments: Assignment[]): Assignment[] {
  const q = text.trim().toLowerCase();
  if (!q) return [];
  const tokens = q.replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter((t) => t.length >= 4);
  return assignments.filter((a) => {
    const title = a.title.toLowerCase();
    if (q.includes(title)) return true;
    if (title.length >= 8 && q.includes(title.slice(0, Math.min(20, title.length)))) return true;
    return tokens.some((tok) => title.includes(tok));
  });
}

export function pickAssignmentForFollowUp(
  text: string,
  assignments: Assignment[],
  priorAssignmentId: string | null,
): Assignment | null {
  const matches = matchAssignmentsInText(text, assignments);
  if (matches.length === 1) return matches[0]!;
  if (matches.length > 1) return null;
  if (priorAssignmentId && isFollowUpEntityPrompt(text)) {
    const prior = assignments.find((a) => a.id === priorAssignmentId);
    if (prior) return prior;
  }
  if (isFollowUpEntityPrompt(text) && assignments.length === 1) return assignments[0]!;
  return null;
}
