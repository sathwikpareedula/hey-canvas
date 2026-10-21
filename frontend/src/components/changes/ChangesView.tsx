"use client";

import { useEffect, useState } from "react";
import { ChangeTimeline } from "@/components/changes/ChangeTimeline";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useDemoDataBadge } from "@/hooks/useDemoDataBadge";
import type { ChangeEvent } from "@/lib/domain/types";

export function ChangesView() {
  const api = useAcademicApi();
  const showDemoHint = useDemoDataBadge();
  const [events, setEvents] = useState<ChangeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api
      .getChanges(50)
      .then(setEvents)
      .catch((err) => setError(err))
      .finally(() => setLoading(false));
  }, [api]);

  if (loading) return <LoadingState />;
  if (error) return <ApiErrorPanel error={error} />;
  if (!events.length) return <EmptyState title="No changes recorded" />;

  return (
    <div className="mx-auto max-w-2xl">
      <p className="mb-4 text-sm text-[var(--muted)]">
        {showDemoHint
          ? "Sample change history for demo data."
          : "Change history from your local Canvas sync on this computer."}
      </p>
      <ChangeTimeline events={events} />
    </div>
  );
}
