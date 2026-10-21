import type { AssistantBlock, ChatMessage } from "@/lib/domain/types";
const ID_LIKE = /\b[a-f0-9-]{8,}\b/i;
const PRACTICE_ID = /\bpractice:[a-f0-9]+\b/gi;
const STUDY_ID = /\bstudy:[a-f0-9]+\b/gi;
const URL_LIKE = /https?:\/\//i;
const TOKEN_LIKE = /\b(token|confirmation)[:\s][\w-]+\b/gi;

export function summarizeMessageForSpeech(message: ChatMessage): string {
  if (message.text?.trim()) {
    return clip(sanitizeSpeech(message.text));
  }
  const parts: string[] = [];
  for (const block of message.blocks ?? []) {
    const line = summarizeBlock(block);
    if (line) parts.push(line);
  }
  return clip(parts.join(" "));
}

export function summarizeBlock(block: AssistantBlock): string {
  switch (block.type) {
    case "text":
    case "warning":
    case "error":
      return block.content ? sanitizeSpeech(block.content) : "";
    case "deadlines": {
      const n = block.assignments?.length ?? 0;
      if (!n) return "No deadlines found.";
      const titles = block.assignments!.slice(0, 3).map((a) => a.title);
      return `You have ${n} upcoming deadlines. ${titles.join(". ")}`;
    }
    case "assignment_summary": {
      const a = block.assignments?.[0];
      return a
        ? `Assignment context for ${a.title}. ${sanitizeSpeech(block.content ?? "")}`
        : sanitizeSpeech(block.content ?? "");
    }
    case "changes_summary": {
      const n = block.changes?.length ?? 0;
      if (!n) return "No recent changes.";
      const labels = block.changes!.slice(0, 3).map((c) => c.entityLabel);
      return `${n} recent updates. ${labels.join(". ")}`;
    }
    case "study":
    case "study_plan": {
      if (block.studySession) {
        const steps = block.studySession.steps.map((s) => s.title).slice(0, 5);
        return `Study plan: ${block.studySession.goal}. Steps: ${steps.join(", ")}.`;
      }
      if (block.studyTips?.length) {
        return `Study plan: ${block.studyTips.slice(0, 4).join(". ")}`;
      }
      return sanitizeSpeech(block.content ?? "Study plan ready.");
    }
    case "practice_question": {
      const q = block.practiceSession?.question?.question;
      return q ? `Practice question: ${sanitizeSpeech(q)}` : "Practice question ready.";
    }
    case "practice_feedback": {
      const fb = block.practiceFeedback;
      if (!fb) return "";
      const verdict = fb.correct ? "Correct." : "Not quite.";
      return `${verdict} ${sanitizeSpeech(fb.feedback)}${fb.hint ? ` Hint: ${sanitizeSpeech(fb.hint)}` : ""}`;
    }
    case "study_guide": {
      const g = block.studyGuide;
      if (!g) return "Study guide ready.";
      const concepts = g.keyConcepts.slice(0, 3).join(", ");
      return `Study guide: ${g.title}. Key ideas: ${concepts}.`;
    }
    case "notification_summary": {
      const n = block.notificationItems?.length ?? 0;
      if (!n) return "No notifications.";
      const titles = block.notificationItems!.slice(0, 2).map((i) => i.title);
      return `${n} notifications. ${titles.join(". ")}`;
    }
    case "reminder_preview": {
      const p = block.reminderPreview;
      return p ? `${p.title}. ${sanitizeSpeech(p.summary)}` : "";
    }
    case "calendar_action_preview": {
      const e = block.calendarPreview?.event;
      return e
        ? `Calendar preview for ${e.summary}. Open the app to confirm before anything is added.`
        : "Calendar preview ready. Confirm in the app.";
    }
    case "calendar_action_result":
      return sanitizeSpeech(block.calendarResult?.message ?? "Calendar update complete.");
    case "document_answer":
      return block.content
        ? sanitizeSpeech(block.content)
        : "Answer includes material evidence. Check the screen for sources.";
    default:
      return sanitizeSpeech(block.content ?? "");
  }
}

function sanitizeSpeech(text: string): string {
  let out = text.replace(/\s+/g, " ").trim();
  out = out.replace(URL_LIKE, "");
  out = out.replace(PRACTICE_ID, "");
  out = out.replace(STUDY_ID, "");
  out = out.replace(TOKEN_LIKE, "");
  out = out.replace(ID_LIKE, "");
  return out.replace(/\s{2,}/g, " ").trim();
}

function clip(text: string, max = 500): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}
