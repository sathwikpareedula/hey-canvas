import { AssistantBlockView } from "@/components/chat/blocks/AssistantBlockView";
import { FollowUpChips } from "@/components/chat/blocks/FollowUpChips";
import { consolidateFollowUps } from "@/lib/chat/consolidate-follow-ups";
import type { AssistantBlock, Course } from "@/lib/domain/types";

export function AssistantResponse({
  blocks,
  coursesById,
  onFollowUp,
  onPracticeAnswer,
  practiceBusy,
}: {
  blocks: AssistantBlock[];
  coursesById: Map<string, Course>;
  onFollowUp?: (prompt: string) => void;
  onPracticeAnswer?: (sessionId: string, answer: string) => void;
  practiceBusy?: boolean;
}) {
  const followUps = consolidateFollowUps(blocks);
  const contentBlocks = blocks.map((b) => ({ ...b, followUps: undefined }));

  return (
    <div className="assistant-answer space-y-3" aria-label="Assistant answer">
      {contentBlocks.map((block, i) => (
        <AssistantBlockView
          key={`${block.type}-${i}`}
          block={block}
          coursesById={coursesById}
          showFollowUps={false}
          onPracticeAnswer={onPracticeAnswer}
          practiceBusy={practiceBusy}
        />
      ))}
      <FollowUpChips items={followUps.length ? followUps : undefined} onSelect={onFollowUp} />
    </div>
  );
}
