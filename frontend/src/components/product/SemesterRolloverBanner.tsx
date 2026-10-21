"use client";

import Link from "next/link";
import { useFocusCourses } from "@/contexts/FocusCoursesContext";

export function SemesterRolloverBanner() {
  const { rolloverHint } = useFocusCourses();
  if (!rolloverHint) return null;
  return (
    <div
      className="rounded-xl border border-[var(--warn-border)] bg-[var(--warn-bg)] px-4 py-3 text-sm text-[var(--warn-text)]"
      role="status"
    >
      {rolloverHint}{" "}
      <Link href="/settings#focus-courses" className="font-medium underline">
        Update focus courses
      </Link>
    </div>
  );
}
