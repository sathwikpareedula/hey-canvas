"use client";

import { useEffect, useState } from "react";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import {
  STARTING_LEVEL_LABELS,
  TEACHING_DEPTH_LABELS,
  type CourseProfile,
  type CourseProfileData,
  type TeachingDepth,
} from "@/lib/domain/course-intelligence";

export function CourseProfileSettings({ courseId }: { courseId: string }) {
  const api = useAcademicApi();
  const [profile, setProfile] = useState<CourseProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    api
      .getCourseProfile(courseId)
      .then((p) => {
        if (active) setProfile(p);
      })
      .catch((err) => {
        if (active) setError(err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, courseId]);

  const prefs = profile?.effectivePreferences;

  const save = async (patch: Partial<CourseProfileData>) => {
    setSaving(true);
    setError(null);
    try {
      const next = await api.updateCourseProfile(courseId, patch);
      setProfile(next);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ApiErrorPanel error={error} onRetry={() => window.location.reload()} />;
  if (!profile || !prefs) {
    return (
      <p className="text-sm text-[var(--muted)]">
        Course study preferences are not available from the backend yet.
      </p>
    );
  }

  return (
    <form
      className="space-y-4 rounded-xl border border-[var(--border)] p-4"
      onSubmit={(e) => e.preventDefault()}
    >
      <p className="text-xs text-[var(--muted)]">
        These settings shape how Hey Canvas explains material for this course when a real assistant
        API is connected. Nothing here contacts Canvas directly.
      </p>
      <label className="block text-sm">
        Teaching depth
        <select
          value={prefs.teachingDepth}
          disabled={saving}
          onChange={(e) =>
            void save({ teachingDepth: e.target.value as TeachingDepth })
          }
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2"
        >
          {(Object.keys(TEACHING_DEPTH_LABELS) as TeachingDepth[]).map((k) => (
            <option key={k} value={k}>{TEACHING_DEPTH_LABELS[k]}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        Starting level
        <select
          value={prefs.startingLevel}
          disabled={saving}
          onChange={(e) =>
            void save({
              startingLevel: e.target.value as CourseProfileData["startingLevel"],
            })
          }
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2"
        >
          {(Object.keys(STARTING_LEVEL_LABELS) as CourseProfileData["startingLevel"][]).map(
            (k) => (
              <option key={k} value={k}>{STARTING_LEVEL_LABELS[k]}</option>
            ),
          )}
        </select>
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={prefs.stepByStep ?? false}
          disabled={saving}
          onChange={(e) => void save({ stepByStep: e.target.checked })}
        />
        Prefer step-by-step explanations
      </label>
      <label className="block text-sm">
        Course instructions (bounded)
        <textarea
          value={profile.effectiveCourseInstructions ?? ""}
          disabled={saving}
          maxLength={4000}
          rows={3}
          onChange={(e) => void save({ studyInstructions: e.target.value })}
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
        />
      </label>
    </form>
  );
}
