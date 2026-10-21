import { formatChicagoDateTime } from "@/lib/utils/chicago-date";

export function formatDueDate(iso: string | null | undefined): string {
  if (!iso) return "No due date";
  return formatChicagoDateTime(iso);
}

export function formatRelativeTime(iso: string): string {
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function deadlineWindowLabel(
  window: string | undefined,
): string | null {
  switch (window) {
    case "past_due_time":
      return "Past due time";
    case "today":
      return "Due today";
    case "tomorrow":
      return "Due tomorrow";
    case "this_week":
      return "This week";
    case "next_7_days":
      return "Next 7 days";
    case "upcoming":
      return "Upcoming";
    default:
      return null;
  }
}
