import type { AcademicNotificationType, NotificationSeverity } from "@/lib/domain/planning";
import type { AppNotification, NotificationCategory } from "@/lib/domain/types";

type BackendNotification = {
  id: string;
  course_id: string;
  assignment_id?: string | null;
  notification_type: string;
  severity: string;
  title: string;
  message: string;
  due_at?: string | null;
  source?: string;
  observed_at: string;
  dedupe_key?: string;
  read: boolean;
  dismissed: boolean;
};

export function mapNotificationTypeToCategory(type: string): NotificationCategory {
  switch (type) {
    case "professor_material_new":
    case "professor_material_changed":
      return "new_material";
    case "assignment_due_date_changed":
      return "canvas_change";
    default:
      return "deadline";
  }
}

export function mapNotificationHref(item: {
  notificationType: AcademicNotificationType;
  assignmentId?: string | null;
  courseId: string;
}): string | undefined {
  if (item.assignmentId) return `/assignments/${item.assignmentId}`;
  if (
    item.notificationType === "professor_material_new" ||
    item.notificationType === "professor_material_changed"
  ) {
    return `/courses/${item.courseId}`;
  }
  if (item.notificationType === "assignment_due_date_changed") return "/changes";
  return `/courses/${item.courseId}`;
}

export function mapBackendNotification(row: BackendNotification): AppNotification {
  const notificationType = row.notification_type as AcademicNotificationType;
  return {
    id: row.id,
    category: mapNotificationTypeToCategory(row.notification_type),
    notificationType,
    severity: row.severity as NotificationSeverity,
    title: row.title,
    body: row.message,
    createdAt: row.observed_at,
    dueAt: row.due_at ?? undefined,
    read: row.read,
    dismissed: row.dismissed,
    courseId: row.course_id,
    assignmentId: row.assignment_id ?? undefined,
    href: mapNotificationHref({
      notificationType,
      assignmentId: row.assignment_id,
      courseId: row.course_id,
    }),
  };
}

export function mapBackendNotificationList(body: {
  items?: BackendNotification[];
  total?: number;
}): AppNotification[] {
  const items = Array.isArray(body.items) ? body.items : [];
  return items.map(mapBackendNotification);
}
