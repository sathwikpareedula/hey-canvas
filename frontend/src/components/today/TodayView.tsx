"use client";

import { useEffect, useMemo, useState } from "react";
import { DeadlineGroup } from "@/components/assignment/DeadlineGroup";
import { ChangeTimeline } from "@/components/changes/ChangeTimeline";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { ChangeEvent, Course, DeadlinesGrouped } from "@/lib/domain/types";

export function TodayView() {
  const api = useAcademicApi();
  const [courses, setCourses] = useState<Course[]>([]);
  const [deadlines, setDeadlines] = useState<DeadlinesGrouped | null>(null);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const coursesById = useMemo(() => new Map(courses.map((c) => [c.id, c])), [courses]);

  const retry = () => {
    setError(null);
    setLoading(true);
    Promise.all([api.getCourses(), api.getDeadlines(), api.getChanges(5)])
      .then(([c, d, ch]) => {
        setCourses(c);
        setDeadlines(d);
        setChanges(ch);
      })
      .catch((err) => setError(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let active = true;
    Promise.all([api.getCourses(), api.getDeadlines(), api.getChanges(5)])
      .then(([c, d, ch]) => {
        if (!active) return;
        setCourses(c);
        setDeadlines(d);
        setChanges(ch);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  if (loading) return <LoadingState />;
  if (error) return <ApiErrorPanel error={error} onRetry={retry} />;
  if (!deadlines) return null;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <DeadlineGroup
        title="Due today"
        assignments={deadlines.today}
        coursesById={coursesById}
      />
      <DeadlineGroup
        title="Due tomorrow"
        assignments={deadlines.tomorrow}
        coursesById={coursesById}
      />
      <DeadlineGroup
        title="This week"
        assignments={deadlines.thisWeek}
        coursesById={coursesById}
      />
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight">Recently changed</h2>
        <ChangeTimeline events={changes} />
      </section>
    </div>
  );
}
