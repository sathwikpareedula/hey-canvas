import type { AssistantBlock } from "@/lib/domain/types";

export function consolidateFollowUps(blocks: AssistantBlock[]): string[] {
  return [...new Set(blocks.flatMap((b) => b.followUps ?? []))];
}
