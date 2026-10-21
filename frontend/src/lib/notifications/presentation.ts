import type { AcademicNotificationType } from "@/lib/domain/planning";
import type { AppNotification } from "@/lib/domain/types";

export function notificationTypeLabel(type?: AcademicNotificationType): string {
  switch (type) {
    case "assignment_due_soon":
      return "Due soon";
    case "assignment_due_tomorrow":
      return "Due tomorrow";
    case "assignment_overdue":
      return "Overdue";
    case "assignment_new":
      return "New assignment";
    case "assignment_due_date_changed":
      return "Deadline changed";
    case "professor_material_new":
      return "New material";
    case "professor_material_changed":
      return "Material updated";
    case "exam_upcoming":
      return "Exam upcoming";
    default:
      return "Update";
  }
}

export function severityTone(severity?: AppNotification["severity"]): string {
  switch (severity) {
    case "critical":
      return "border-l-[var(--danger-border)]";
    case "high":
      return "border-l-[var(--warn-border)]";
    case "medium":
      return "border-l-[var(--accent)]";
    default:
      return "border-l-[var(--border)]";
  }
}
