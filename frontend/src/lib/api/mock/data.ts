/**
 * Development-only mock data. Clearly labeled sample content — not real professor materials.
 */

import type {
  AppNotification,
  Assignment,
  AssignmentDetail,
  ChangeEvent,
  ChatMessage,
  Course,
  DocumentDetail,
  DocumentSearchResult,
  Module,
  ModuleItem,
  SyncRun,
} from "@/lib/domain/types";

const now = new Date();
const iso = (d: Date) => d.toISOString();

const startOfDay = (d: Date) => {
  const x = new Date(d);
  x.setHours(17, 0, 0, 0);
  return x;
};

const addDays = (d: Date, n: number) => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};

export const MOCK_COURSES: Course[] = [
  {
    id: "course-robots",
    name: "Autonomous Robots",
    code: "CSE 4V95",
    term: "Spring 2026",
    color: "#2563eb",
  },
  {
    id: "course-nn",
    name: "Neural Networks",
    code: "CSE 4301",
    term: "Spring 2026",
    color: "#7c3aed",
  },
  {
    id: "course-ml",
    name: "Machine Learning",
    code: "CSE 4309",
    term: "Spring 2026",
    color: "#059669",
  },
  {
    id: "course-sec",
    name: "Secure Programming",
    code: "CSE 3320",
    term: "Spring 2026",
    color: "#dc2626",
  },
  {
    id: "course-csdp",
    name: "Computer System Design Project I",
    code: "CSE 3310",
    term: "Spring 2026",
    color: "#d97706",
  },
];

export const MOCK_ASSIGNMENTS: Assignment[] = [
  {
    id: "asgn-robots-quiz",
    courseId: "course-robots",
    title: "Robotics Quiz 2 (sample)",
    dueAt: iso(startOfDay(now)),
    pointsPossible: 20,
    deadlineWindow: "today",
  },
  {
    id: "asgn-nn-hw",
    courseId: "course-nn",
    title: "Homework 3 — backprop (sample)",
    dueAt: iso(startOfDay(now)),
    pointsPossible: 50,
    deadlineWindow: "today",
  },
  {
    id: "asgn-ml-lab",
    courseId: "course-ml",
    title: "Lab report draft (sample)",
    dueAt: iso(startOfDay(addDays(now, 1))),
    pointsPossible: 30,
    deadlineWindow: "tomorrow",
  },
  {
    id: "asgn-sec-proj",
    courseId: "course-sec",
    title: "Buffer overflow write-up (sample)",
    dueAt: iso(startOfDay(addDays(now, 2))),
    pointsPossible: 100,
    deadlineWindow: "this_week",
  },
  {
    id: "asgn-csdp-milestone",
    courseId: "course-csdp",
    title: "Milestone 2 demo notes (sample)",
    dueAt: iso(startOfDay(addDays(now, 5))),
    pointsPossible: 75,
    deadlineWindow: "this_week",
  },
  {
    id: "asgn-robots-hw",
    courseId: "course-robots",
    title: "Homework 2 — kinematics (sample)",
    dueAt: iso(startOfDay(addDays(now, -3))),
    pointsPossible: 40,
    deadlineWindow: "past_due_time",
  },
  {
    id: "asgn-robots-plan",
    courseId: "course-robots",
    title: "Path-planning worksheet (sample)",
    dueAt: iso(startOfDay(addDays(now, 4))),
    pointsPossible: 25,
    deadlineWindow: "this_week",
  },
];

export const MOCK_MODULES: Module[] = [
  {
    id: "mod-robots-1",
    courseId: "course-robots",
    name: "Week 6 — Motion Planning",
    position: 1,
  },
  {
    id: "mod-nn-1",
    courseId: "course-nn",
    name: "Unit 4 — Training",
    position: 1,
  },
];

export const MOCK_MODULE_ITEMS: ModuleItem[] = [
  {
    id: "mi-robots-lec",
    moduleId: "mod-robots-1",
    courseId: "course-robots",
    title: "Lecture 06 (sample PDF)",
    type: "File",
    position: 1,
  },
  {
    id: "mi-robots-hw",
    moduleId: "mod-robots-1",
    courseId: "course-robots",
    title: "Homework 2 — instructions (sample)",
    type: "Assignment",
    position: 2,
  },
];

export const MOCK_SEARCH_RESULTS: DocumentSearchResult[] = [
  {
    documentId: "doc-robots-lec06",
    title: "Lecture 06.pdf (sample)",
    courseId: "course-robots",
    courseName: "Autonomous Robots",
    snippet:
      "...sample excerpt discussing inverse kinematics for a 2-DOF arm (mock text only)...",
    unit: { page: 17, label: "Page 17" },
    documentType: "pdf",
    provenance: {
      courseId: "course-robots",
      courseName: "Autonomous Robots",
      moduleName: "Week 6 — Motion Planning",
      moduleItemTitle: "Lecture 06 (sample PDF)",
      fileName: "Lecture 06.pdf (sample)",
      documentTitle: "Lecture 06 (sample)",
      unit: { page: 17, label: "Page 17" },
      excerpt:
        "Sample provenance excerpt — not from a real downloaded document.",
    },
  },
  {
    documentId: "doc-robots-hw2",
    title: "Homework 2 — instructions (sample)",
    courseId: "course-robots",
    courseName: "Autonomous Robots",
    snippet: "...sample instructions reference Jacobian matrices (mock)...",
    unit: { section: "Problem 3", label: "Problem 3" },
    documentType: "assignment",
    provenance: {
      courseId: "course-robots",
      courseName: "Autonomous Robots",
      moduleItemTitle: "Homework 2 — instructions (sample)",
      documentTitle: "Homework 2 (sample)",
      unit: { section: "Problem 3", label: "Problem 3" },
    },
  },
];

export const MOCK_CHANGES: ChangeEvent[] = [
  {
    id: "chg-1",
    observedAt: iso(addDays(now, 0)),
    courseId: "course-robots",
    courseName: "Autonomous Robots",
    entityType: "assignment",
    entityLabel: "Robotics Quiz 2 (sample)",
    eventType: "deadline_changed",
    fieldName: "due_at",
    oldValue: "2026-03-10T22:00:00Z",
    newValue: iso(startOfDay(now)),
  },
  {
    id: "chg-2",
    observedAt: iso(addDays(now, -1)),
    courseId: "course-nn",
    courseName: "Neural Networks",
    entityType: "module_item",
    entityLabel: "Lecture slides — week 5 (sample)",
    eventType: "module_item_created",
  },
  {
    id: "chg-3",
    observedAt: iso(addDays(now, -1)),
    courseId: "course-ml",
    courseName: "Machine Learning",
    entityType: "file",
    entityLabel: "dataset_notes.pdf (sample)",
    eventType: "file_metadata_changed",
    fieldName: "display_name",
    oldValue: "notes.pdf",
    newValue: "dataset_notes.pdf (sample)",
  },
  {
    id: "chg-4",
    observedAt: iso(addDays(now, -2)),
    courseId: "course-sec",
    courseName: "Secure Programming",
    entityType: "file",
    entityLabel: "lab3_binary (sample)",
    eventType: "local_file_integrity_issue",
    newValue: "checksum mismatch on local copy (sample event)",
  },
];

export const MOCK_SYNC_RUNS: SyncRun[] = [
  {
    id: 42,
    startedAt: iso(addDays(now, 0)),
    finishedAt: iso(addDays(now, 0)),
    status: "succeeded",
    trigger: "cli",
    changeEventsCreated: 3,
    errorCount: 0,
    stageResults: {
      courses: { status: "succeeded", counts: { updated: 2 } },
      assignments: { status: "succeeded", counts: { updated: 5 } },
      modules: { status: "succeeded", counts: { updated: 1 } },
    },
    changeSummary: {
      deadline_changes: 1,
      module_item_changes: 1,
      file_metadata_changes: 1,
    },
    errors: [],
  },
  {
    id: 41,
    startedAt: iso(addDays(now, -2)),
    finishedAt: iso(addDays(now, -2)),
    status: "partially_succeeded",
    trigger: "cli",
    changeEventsCreated: 1,
    errorCount: 2,
    stageResults: {
      courses: { status: "succeeded" },
      assignments: { status: "partially_succeeded" },
      files: { status: "failed", reason: "sample stage failure" },
    },
    changeSummary: { module_item_changes: 1 },
    errors: [
      { stage: "files", message: "Sample: metadata sync issue (mock)" },
      { stage: "assignments", message: "Sample: one course skipped (mock)" },
    ],
  },
];

export const MOCK_ASSIGNMENT_DETAILS: Record<string, AssignmentDetail> = {
  "asgn-robots-quiz": {
    ...MOCK_ASSIGNMENTS[0],
    descriptionPlainText:
      "Sample quiz instructions (mock plain text).\n\nReview Lecture 06 sample notes on motion planning.\nNo real Canvas HTML is rendered in the UI.",
    moduleContext: "Week 6 — Motion Planning",
    relatedDocumentIds: ["doc-robots-lec06"],
    recentChangeIds: ["chg-1"],
  },
  "asgn-robots-hw": {
    ...MOCK_ASSIGNMENTS[5],
    descriptionPlainText:
      "Sample homework description discussing Jacobian matrices and inverse kinematics (mock only).",
    moduleContext: "Week 6 — Motion Planning",
    relatedDocumentIds: ["doc-robots-hw2", "doc-robots-lec06"],
    recentChangeIds: [],
  },
};

export const MOCK_DOCUMENT_DETAILS: Record<string, DocumentDetail> = {
  "doc-robots-lec06": {
    id: "doc-robots-lec06",
    courseId: "course-robots",
    courseName: "Autonomous Robots",
    title: "Lecture 06.pdf (sample)",
    documentType: "pdf",
    provenance: MOCK_SEARCH_RESULTS[0].provenance,
    previewPlainText:
      "Sample parsed lecture text (mock).\n\nPage 17 discusses inverse kinematics for a planar manipulator.\nThis is not extracted from a real downloaded PDF.",
    ingestionState: "searchable",
    units: [
      { page: 1, label: "Page 1" },
      { page: 17, label: "Page 17" },
    ],
    technical: {
      contentSha256: "sample-sha256-not-real",
      parserVersion: "mock-0.1",
    },
  },
  "doc-robots-hw2": {
    id: "doc-robots-hw2",
    courseId: "course-robots",
    courseName: "Autonomous Robots",
    title: "Homework 2 — instructions (sample)",
    documentType: "assignment",
    provenance: MOCK_SEARCH_RESULTS[1].provenance,
    previewPlainText: "Sample homework instructions text (mock). Problem 3: Jacobian practice.",
    ingestionState: "indexed",
    units: [{ section: "Problem 3", label: "Problem 3" }],
  },
};

export const MOCK_NOTIFICATIONS: AppNotification[] = [
  {
    id: "n-1",
    category: "deadline",
    title: "Robotics Quiz 2 (sample)",
    body: "Due today — sample reminder only.",
    createdAt: iso(now),
    read: false,
    href: "/assignments/asgn-robots-quiz",
  },
  {
    id: "n-2",
    category: "canvas_change",
    title: "Deadline changed",
    body: "Autonomous Robots — Robotics Quiz 2 (sample)",
    createdAt: iso(addDays(now, -1)),
    read: false,
    href: "/changes",
  },
  {
    id: "n-3",
    category: "new_material",
    title: "Lecture 06 (sample)",
    body: "New material indexed in Autonomous Robots (mock).",
    createdAt: iso(addDays(now, -1)),
    read: true,
    href: "/materials/doc-robots-lec06",
  },
  {
    id: "n-4",
    category: "sync_problem",
    title: "Partial sync",
    body: "Last run partially succeeded — 2 sample errors.",
    createdAt: iso(addDays(now, -2)),
    read: true,
    href: "/sync",
  },
];

export const MOCK_GREETING_HOUR = (): "morning" | "afternoon" | "evening" => {
  const h = now.getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
};

export const MOCK_SAMPLE_CONVERSATION: ChatMessage[] = [
  {
    id: "msg-1",
    role: "user",
    createdAt: iso(now),
    text: "What's due today?",
  },
  {
    id: "msg-2",
    role: "assistant",
    createdAt: iso(now),
    blocks: [
      {
        type: "deadlines",
        content:
          "Here is a sample summary based on mock deadline data (not live Canvas).",
        assignments: MOCK_ASSIGNMENTS.filter((a) => a.deadlineWindow === "today"),
      },
      {
        type: "text",
        content:
          "Reminder: “past due time” only means the due timestamp has passed — not whether something was submitted.",
      },
    ],
  },
];
