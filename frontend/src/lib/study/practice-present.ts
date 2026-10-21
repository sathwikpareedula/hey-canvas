import type { PracticeSession } from "@/lib/domain/study-workflows";
import { finiteNumber, finitePercent } from "@/lib/utils/numbers";
import { displayText } from "@/lib/utils/display-text";

export function practiceProgressLabel(session: PracticeSession): string {
  const index = finiteNumber(session.questionIndex, 0) + 1;
  const total = Math.max(finiteNumber(session.totalQuestions, 0), index);
  const progress = finitePercent(session.progress, 0);
  return `Progress ${progress}% · Question ${index} of ${total}`;
}

export function practiceTopicLabel(topic: string): string {
  return displayText(topic, "Practice");
}
