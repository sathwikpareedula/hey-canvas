import Link from "next/link";
import { EmptyState } from "@/components/ui/EmptyState";

export default function AppNotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="This route does not exist in Hey Canvas yet."
      action={
        <Link href="/dashboard" className="text-sm text-[var(--accent)] underline">
          Go to Dashboard
        </Link>
      }
    />
  );
}
