"use client";

import { ErrorState } from "@/components/ui/ErrorState";

export default function AppError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState
      message="Something went wrong loading this page. Try again or return to the dashboard."
      onRetry={reset}
    />
  );
}
