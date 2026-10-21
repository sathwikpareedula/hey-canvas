export type StudyMode = "learn" | "review" | "practice" | "exam";

export const STUDY_MODE_OPTIONS: {
  id: StudyMode;
  label: string;
  description: string;
}[] = [
  { id: "learn", label: "Learn", description: "Step-by-step explanations from your materials" },
  { id: "review", label: "Review", description: "Refresh key ideas before class or labs" },
  { id: "practice", label: "Practice", description: "Guided practice without submitting work" },
  { id: "exam", label: "Exam prep", description: "Focus on high-yield topics and timing" },
];

export function parseStudyMode(raw: string | null): StudyMode | null {
  if (!raw) return null;
  return STUDY_MODE_OPTIONS.some((m) => m.id === raw) ? (raw as StudyMode) : null;
}
