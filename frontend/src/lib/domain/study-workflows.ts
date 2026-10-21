/** Study session, practice, and study guide contracts (backend 47c2690). */

export type BackendStudyMode = "learn" | "review" | "practice" | "exam_prep";

export type StudySessionStatus = "active" | "paused" | "completed";

export interface EvidenceReference {
  authority: string;
  identifier: string;
  locator?: string | null;
}

export interface StudyStep {
  order: number;
  title: string;
  minutes: number;
  status: string;
}

export interface StudySessionCreateRequest {
  courseId: string;
  goal: string;
  durationMinutes: number;
  topics: string[];
  studyMode: BackendStudyMode;
  assignmentIds: string[];
}

export interface StudySession {
  sessionId: string;
  courseId: string;
  goal: string;
  durationMinutes: number;
  topics: string[];
  studyMode: BackendStudyMode;
  assignmentIds: string[];
  status: StudySessionStatus;
  relevantEvidence: EvidenceReference[];
  steps: StudyStep[];
  progress: number;
}

export interface PracticeQuestion {
  question: string;
  generated: boolean;
  evidence: EvidenceReference[];
}

export interface PracticeSession {
  sessionId: string;
  courseId: string;
  topic: string;
  status: string;
  questionIndex: number;
  totalQuestions: number;
  correctAnswers: number;
  question: PracticeQuestion | null;
  progress: number;
}

export interface PracticeFeedback {
  correct: boolean;
  feedback: string;
  hint: string | null;
  nextQuestion: PracticeQuestion | null;
  progress: number;
}

export interface StudyGuideRequest {
  courseId: string;
  topic?: string;
  assignmentId?: string;
  documentId?: string;
  studyMode?: BackendStudyMode;
}

export interface StudyGuide {
  title: string;
  scope: string;
  keyConcepts: string[];
  explanations: string[];
  evidence: EvidenceReference[];
  reviewChecklist: string[];
  practicePrompts: string[];
  uncertainties: string[];
}
