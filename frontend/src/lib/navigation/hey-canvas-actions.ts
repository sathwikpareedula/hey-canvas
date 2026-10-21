import type { StudyMode } from "@/lib/domain/study-mode";
import { buildHeyCanvasUrl } from "@/lib/navigation/hey-canvas";

export interface HeyCanvasAction {
  id: string;
  label: string;
  prompt: string;
  assignmentId?: string;
  documentId?: string;
  courseId?: string;
}

export function assignmentHeyCanvasActions(
  assignmentTitle: string,
  ctx: { assignmentId: string; courseId: string },
): HeyCanvasAction[] {
  const titled = assignmentTitle ? `“${assignmentTitle}”` : "this assignment";
  return [
    {
      id: "explain",
      label: "Explain this assignment",
      prompt: `Explain what ${titled} is asking for in plain language.`,
    },
    {
      id: "start",
      label: "Help me start",
      prompt: `Help me break ${titled} into a realistic first step I can do today.`,
    },
    {
      id: "need-to-know",
      label: "What do I need to know?",
      prompt: `What do I need to know before starting ${titled}?`,
    },
    {
      id: "submit",
      label: "What do I need to submit?",
      prompt: `What do I need to submit for ${titled}? List deliverables and formats only — do not do the work for me.`,
    },
    {
      id: "prereq",
      label: "Teach prerequisites",
      prompt: `Teach me the prerequisites I need for ${titled}, using course materials where possible.`,
    },
    {
      id: "materials",
      label: "Find relevant professor material",
      prompt: `What professor materials should I review before working on ${titled}?`,
    },
    {
      id: "plan",
      label: "Make a study/work plan",
      prompt: `Create a study plan for ${titled} without doing the work for me.`,
    },
    {
      id: "ask",
      label: "Ask Hey Canvas",
      prompt: `I have questions about ${titled}.`,
    },
  ].map((a) => ({
    ...a,
    assignmentId: ctx.assignmentId,
    courseId: ctx.courseId,
  }));
}

export function materialHeyCanvasActions(
  materialTitle: string,
  ctx: { documentId: string; courseId: string },
): HeyCanvasAction[] {
  const titled = materialTitle ? `“${materialTitle}”` : "this material";
  return [
    {
      id: "explain",
      label: "Explain this material",
      prompt: `Explain the main ideas in ${titled}.`,
    },
    {
      id: "page",
      label: "Explain this page/slide",
      prompt: `Explain the main ideas on the page or slide I'm viewing in ${titled}.`,
    },
    {
      id: "summarize",
      label: "Summarize this section",
      prompt: `Summarize the key concepts from the section I'm studying in ${titled}.`,
    },
    {
      id: "related-material",
      label: "Find related material",
      prompt: `Find other course materials related to ${titled}.`,
    },
    {
      id: "teach",
      label: "Teach me from the beginning",
      prompt: `Teach me ${titled} from the beginning, checking my understanding as we go.`,
    },
    {
      id: "quiz",
      label: "Quiz me on this",
      prompt: `Quiz me on ${titled}. Do not submit anything to Canvas.`,
    },
    {
      id: "related",
      label: "Find related assignments",
      prompt: `Which assignments in this course relate to ${titled}?`,
    },
  ].map((a) => ({
    ...a,
    documentId: ctx.documentId,
    courseId: ctx.courseId,
  }));
}

export function heyCanvasActionHref(
  action: HeyCanvasAction & { assignmentId?: string; documentId?: string; courseId?: string },
  studyMode?: StudyMode,
): string {
  return buildHeyCanvasUrl({
    courseId: action.courseId,
    assignmentId: action.assignmentId,
    documentId: action.documentId,
    prompt: action.prompt,
    studyMode,
  });
}
