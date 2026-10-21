import type { AssistantBlock } from "@/lib/domain/types";

export function isPracticeSessionCompleteBlock(block: AssistantBlock): boolean {
  if (block.type !== "practice_feedback" || !block.practiceFeedback) return false;
  const { practiceFeedback: fb } = block;
  return fb.progress >= 100 && !fb.nextQuestion;
}

export function shouldClearActivePracticeSession(blocks: AssistantBlock[] | undefined): boolean {
  if (!blocks?.length) return false;
  return blocks.some(isPracticeSessionCompleteBlock);
}
