import type { Assignment, ChatMessage, Course, DeadlinesGrouped } from "@/lib/domain/types";
import { filterAssignmentsForNextWeek } from "@/lib/assignments/deadline-selection";
import { formatDueDate } from "@/lib/utils/date";
import { coursePrimaryTitle } from "@/lib/courses/display";

export type DeadlineFastWindow =
  | "today"
  | "tomorrow"
  | "this_week"
  | "next_week"
  | "overdue"
  | "priorities";

/** Normalize casual student phrasing before deadline intent matching. */
export function normalizeDeadlineStudentQuery(prompt: string): string {
  let q = prompt.trim().toLowerCase();
  q = q.replace(/\btmrw\b/g, "tomorrow");
  q = q.replace(/\btom\b/g, "tomorrow");
  q = q.replace(/\bnext\s*wk\b/g, "next week");
  q = q.replace(/\bthis\s*wk\b/g, "this week");
  q = q.replace(/\btn\b/g, "tonight");
  q = q.replace(/\bgotta\b/g, "got to");
  return q;
}

export function matchDeadlineFastPath(prompt: string): DeadlineFastWindow | null {
  const q = normalizeDeadlineStudentQuery(prompt);
  if (!q) return null;

  const nextWeekSignal =
    /\bnext week\b/.test(q) &&
    /\b(due|deadline|have|anything|what|asked|show|prepare|work|finish)\b/.test(q);
  if (nextWeekSignal || /\bi asked next week\b/.test(q) || /\bno,? next week\b/.test(q)) {
    return "next_week";
  }

  if (
    /\b(which one should i do first|what should i do first|give me my priorities)\b/.test(q) ||
    (/\bwhat should i work on\b/.test(q) && /\b(tonight|today|now)\b/.test(q))
  ) {
    return "priorities";
  }

  const tomorrowSignal =
    /\btomorrow\b/.test(q) &&
    /\b(due|deadline|have|anything|what|should|finish|got)\b/.test(q);
  if (tomorrowSignal) return "tomorrow";

  if (
    /\b(am i missing|missing anything|anything overdue|most urgent)\b/.test(q) ||
    /\b(overdue|past due|late)\b/.test(q)
  ) {
    return "overdue";
  }

  if (
    /\b(tonight|today)\b/.test(q) &&
    /\b(due|deadline|have|anything|what|work|do)\b/.test(q)
  ) {
    return "today";
  }
  if (
    /\b(nothing|anything)\b.*\b(due)\b/.test(q) &&
    !/\btomorrow\b/.test(q)
  ) {
    return "today";
  }
  if (
    /\bwhat\b.*\b(due today)\b/.test(q) ||
    /\btoday\b.*\b(due|deadline)/.test(q) ||
    q === "what's due today?" ||
    q === "what do i have due today?" ||
    /^bro,? what'?s due\b/.test(q) ||
    /^what'?s due\??$/.test(q) ||
    /\bwhat do i gotta do today\b/.test(q)
  ) {
    return "today";
  }
  if (/\bthis week\b/.test(q) && /\b(due|deadline|have|anything|what)\b/.test(q)) {
    return "this_week";
  }
  return null;
}

function filterByCourse(list: Assignment[], courseId?: string): Assignment[] {
  if (!courseId) return list;
  return list.filter((a) => a.courseId === courseId);
}

function emptyCopy(window: DeadlineFastWindow, scoped: boolean): string {
  const scope = scoped ? "for this course" : "";
  switch (window) {
    case "today":
      return `Nothing due today ${scope}.`.trim();
    case "tomorrow":
      return `Nothing due tomorrow ${scope}.`.trim();
    case "this_week":
      return `Nothing else due this week ${scope}.`.trim();
    case "next_week":
      return `Nothing due next week ${scope}.`.trim();
    case "overdue":
      return `No overdue assignments ${scope} in your synced data.`.trim();
    case "priorities":
      return `No urgent deadlines ${scope} in your synced data.`.trim();
    default:
      return "No matching deadlines in your synced data.";
  }
}

function windowTitle(window: DeadlineFastWindow, scoped: boolean): string {
  const scope = scoped ? " (this course)" : "";
  switch (window) {
    case "today":
      return `Due today${scope}`;
    case "tomorrow":
      return `Due tomorrow${scope}`;
    case "this_week":
      return `Due this week${scope}`;
    case "next_week":
      return `Due next week${scope}`;
    case "overdue":
      return `Overdue${scope}`;
    case "priorities":
      return `What to do first${scope}`;
    default:
      return "Deadlines";
  }
}

const PRIORITY_LIST_LIMIT = 8;

function compareDueAt(a: Assignment, b: Assignment): number {
  const ad = a.dueAt ? Date.parse(a.dueAt) : Number.POSITIVE_INFINITY;
  const bd = b.dueAt ? Date.parse(b.dueAt) : Number.POSITIVE_INFINITY;
  return ad - bd;
}

function buildPriorityAssignments(
  deadlines: DeadlinesGrouped,
  overdue: Assignment[],
  courseId?: string,
): Assignment[] {
  const seen = new Set<string>();
  const out: Assignment[] = [];
  const add = (list: Assignment[]) => {
    for (const a of filterByCourse(list, courseId)) {
      if (seen.has(a.id)) continue;
      seen.add(a.id);
      out.push(a);
    }
  };
  add(overdue);
  add(deadlines.today);
  add(deadlines.tomorrow);
  add(deadlines.thisWeek);
  out.sort(compareDueAt);
  return out.slice(0, PRIORITY_LIST_LIMIT);
}

function formatAssignmentLine(a: Assignment, courses: Map<string, Course>): string {
  const course = courses.get(a.courseId);
  const courseLabel = course ? coursePrimaryTitle(course) : "Course";
  const due = formatDueDate(a.dueAt);
  return `• ${a.title} — ${courseLabel}${due ? ` · ${due}` : ""}`;
}

export function buildDeadlineFastPathMessage(options: {
  window: DeadlineFastWindow;
  deadlines: DeadlinesGrouped;
  overdue: Assignment[];
  courseId?: string;
  courses: Course[];
  allAssignments?: Assignment[];
  now?: Date;
}): ChatMessage {
  const { window, deadlines, overdue, courseId, courses } = options;
  const courseMap = new Map(courses.map((c) => [c.id, c]));
  const scoped = Boolean(courseId);

  let list: Assignment[] = [];
  switch (window) {
    case "today":
      list = filterByCourse(deadlines.today, courseId);
      break;
    case "tomorrow":
      list = filterByCourse(deadlines.tomorrow, courseId);
      break;
    case "this_week":
      list = filterByCourse(deadlines.thisWeek, courseId);
      break;
    case "next_week": {
      if (options.allAssignments) {
        list = filterByCourse(options.allAssignments, courseId);
      } else {
        const pool = [
          ...deadlines.today,
          ...deadlines.tomorrow,
          ...deadlines.thisWeek,
        ];
        list = filterByCourse(filterAssignmentsForNextWeek(pool, options.now), courseId);
      }
      break;
    }
    case "overdue":
      list = filterByCourse(overdue, courseId);
      break;
    case "priorities":
      list = buildPriorityAssignments(deadlines, overdue, courseId);
      break;
  }

  const title = windowTitle(window, scoped);
  const body =
    list.length === 0
      ? emptyCopy(window, scoped)
      : list.map((a) => formatAssignmentLine(a, courseMap)).join("\n");

  return {
    id: `deadline-fast-${Date.now()}`,
    role: "assistant",
    createdAt: new Date().toISOString(),
    status: "complete",
    text: `${title}\n\n${body}`,
    blocks: [
      {
        type: "deadlines",
        content: window,
        assignments: list,
      },
    ],
  };
}
