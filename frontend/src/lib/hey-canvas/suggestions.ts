import type { StudyMode } from "@/lib/domain/study-mode";

export interface HeyCanvasSuggestionContext {
  courseId?: string | null;
  courseName?: string | null;
  assignmentId?: string | null;
  assignmentTitle?: string | null;
  documentId?: string | null;
  documentTitle?: string | null;
  studyMode?: StudyMode | null;
}

/** Starter prompts only — they are sent as user messages, never prefilled answers. */
export function buildHeyCanvasSuggestions(ctx: HeyCanvasSuggestionContext): string[] {
  const course = ctx.courseName ? `in ${ctx.courseName}` : "across my courses";
  const assignment = ctx.assignmentTitle ? `“${ctx.assignmentTitle}”` : "this assignment";
  const material = ctx.documentTitle ? `“${ctx.documentTitle}”` : "this material";

  if (ctx.documentId) {
    const base = [
      `Explain the main ideas in ${material}.`,
      `Summarize the key section of ${material}.`,
      `Quiz me on ${material}. Do not submit anything to Canvas.`,
      `What assignments relate to ${material}?`,
    ];
    if (ctx.studyMode === "learn") {
      base.unshift(`Teach me ${material} from the beginning.`);
    }
    if (ctx.studyMode === "exam") {
      base.unshift(`Help me prepare for an upcoming quiz using ${material}.`);
    }
    return base.slice(0, 6);
  }

  if (ctx.assignmentId) {
    return [
      `Explain what ${assignment} is asking for.`,
      `What do I need to know before starting ${assignment}?`,
      `Find professor materials relevant to ${assignment}.`,
      `Help me break ${assignment} into a realistic first step.`,
      `Make a study plan for ${assignment} without doing the work for me.`,
    ];
  }

  if (ctx.courseId) {
    const coursePrompts = [
      `What do I have due soon ${course}?`,
      `What changed recently ${course}?`,
      `Continue studying ${ctx.courseName ?? "this course"} with me.`,
      `What should I focus on ${course} this week?`,
    ];
    if (ctx.studyMode === "practice") {
      coursePrompts.unshift(`Give me practice questions ${course} without submitting work.`);
    }
    if (ctx.studyMode === "review") {
      coursePrompts.unshift(`Help me review the most important topics ${course}.`);
    }
    if (ctx.studyMode === "exam") {
      coursePrompts.unshift(`Help me prepare for my next exam ${course}.`);
    }
    if (ctx.studyMode === "learn") {
      coursePrompts.unshift(`Teach me the next topic I should learn ${course}.`);
    }
    return coursePrompts.slice(0, 6);
  }

  return [
    "What do I have due today?",
    "What is due tomorrow?",
    "What changed since my last sync?",
    "What should I work on this week?",
    "Search my course materials for a topic.",
    "Help me prepare for my next deadline.",
  ];
}
