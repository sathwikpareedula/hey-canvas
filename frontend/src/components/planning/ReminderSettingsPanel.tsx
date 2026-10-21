"use client";

import { useCallback, useEffect, useState } from "react";
import type { Course } from "@/lib/domain/types";
import { ApiErrorPanel } from "@/components/ui/ApiErrorPanel";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import type { ReminderPreference } from "@/lib/domain/planning";
import { formatDueDate } from "@/lib/utils/date";

const LEAD_OPTIONS = [1, 3, 6, 12, 24, 48, 72];

function parseLeadInput(raw: string): number[] {
  return raw
    .split(/[,;\s]+/)
    .map((s) => Number.parseInt(s.trim(), 10))
    .filter((n) => Number.isFinite(n) && n > 0 && n <= 168);
}

export function ReminderSettingsPanel() {
  const api = useAcademicApi();
  const [prefs, setPrefs] = useState<ReminderPreference | null>(null);
  const [leadInput, setLeadInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [previewAssignment, setPreviewAssignment] = useState({ courseId: "", assignmentId: "" });
  const [preview, setPreview] = useState<Awaited<
    ReturnType<typeof api.previewReminderPlan>
  > | null>(null);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [overrideCourseId, setOverrideCourseId] = useState("");
  const [overrideLeads, setOverrideLeads] = useState("12, 3");

  useEffect(() => {
    api.getCourses().then(setCourses).catch(() => setCourses([]));
  }, [api]);

  useEffect(() => {
    let active = true;
    api
      .getReminderPreferences()
      .then((p) => {
        if (!active) return;
        setPrefs(p);
        setLeadInput(p.leadTimesHours.join(", "));
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

  const save = useCallback(async () => {
    if (!prefs) return;
    const leadTimesHours = parseLeadInput(leadInput);
    if (!leadTimesHours.length) {
      setError(new Error("Add at least one lead time in hours (1–168)."));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const next = await api.saveReminderPreferences({
        ...prefs,
        leadTimesHours,
      });
      setPrefs(next);
      setLeadInput(next.leadTimesHours.join(", "));
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }, [api, prefs, leadInput]);

  const runPreview = useCallback(async () => {
    if (!previewAssignment.courseId || !previewAssignment.assignmentId) {
      setPreviewError(new Error("Enter a course ID and assignment ID from your sync."));
      return;
    }
    setPreviewError(null);
    try {
      const plan = await api.previewReminderPlan(
        previewAssignment.courseId,
        previewAssignment.assignmentId,
      );
      setPreview(plan);
    } catch (err) {
      setPreview(null);
      setPreviewError(err);
    }
  }, [api, previewAssignment]);

  if (loading) {
    return <p className="text-sm text-[var(--muted)]">Loading reminder preferences…</p>;
  }
  if (!prefs) {
    return error ? <ApiErrorPanel error={error} /> : null;
  }

  return (
    <section className="space-y-4 rounded-xl border border-[var(--border)] p-4">
      <h2 className="text-sm font-semibold">Reminder preferences</h2>
      <p className="text-xs text-[var(--muted)]">
        Local reminder plans only — the backend stores preferences and deterministic schedules, not
        push notifications from Canvas.
      </p>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={prefs.enabled}
          onChange={(e) => setPrefs({ ...prefs, enabled: e.target.checked })}
        />
        Reminders enabled
      </label>
      <label className="block text-sm">
        Lead times (hours before due, comma-separated)
        <input
          value={leadInput}
          onChange={(e) => setLeadInput(e.target.value)}
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
          placeholder="24, 3"
        />
      </label>
      <p className="text-xs text-[var(--muted)]">Quick picks:</p>
      <div className="flex flex-wrap gap-2">
        {LEAD_OPTIONS.map((h) => (
          <button
            key={h}
            type="button"
            className="rounded-full border border-[var(--border)] px-2 py-0.5 text-xs"
            onClick={() => {
              const current = parseLeadInput(leadInput);
              if (!current.includes(h)) setLeadInput([...current, h].sort((a, b) => b - a).join(", "));
            }}
          >
            {h}h
          </button>
        ))}
      </div>
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Course overrides</h3>
        <p className="text-xs text-[var(--muted)]">
          Optional per-course lead times (hours). Saved with your preferences.
        </p>
        {Object.entries(prefs.courseOverrides).map(([cid, hours]) => (
          <p key={cid} className="text-xs">
            <span className="font-medium">{courses.find((c) => c.id === cid)?.name ?? cid}</span>
            : {hours.join(", ")}h
            <button
              type="button"
              className="ml-2 underline"
              onClick={() => {
                const next = { ...prefs.courseOverrides };
                delete next[cid];
                setPrefs({ ...prefs, courseOverrides: next });
              }}
            >
              Remove
            </button>
          </p>
        ))}
        <div className="flex flex-wrap gap-2">
          <select
            value={overrideCourseId}
            onChange={(e) => setOverrideCourseId(e.target.value)}
            className="min-h-10 rounded-lg border border-[var(--border)] px-2 text-sm"
            aria-label="Course for override"
          >
            <option value="">Select course</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <input
            value={overrideLeads}
            onChange={(e) => setOverrideLeads(e.target.value)}
            placeholder="12, 3"
            className="min-h-10 rounded-lg border border-[var(--border)] px-2 text-sm"
            aria-label="Override lead hours"
          />
          <button
            type="button"
            className="text-sm underline"
            onClick={() => {
              if (!overrideCourseId) return;
              const hours = parseLeadInput(overrideLeads);
              if (!hours.length) return;
              setPrefs({
                ...prefs,
                courseOverrides: { ...prefs.courseOverrides, [overrideCourseId]: hours },
              });
            }}
          >
            Add override
          </button>
        </div>
      </div>
      <label className="block text-sm">
        Timezone (IANA)
        <input
          value={prefs.timezone}
          onChange={(e) => setPrefs({ ...prefs, timezone: e.target.value })}
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 text-sm"
        />
      </label>
      {error ? <ApiErrorPanel error={error} /> : null}
      <button
        type="button"
        disabled={saving}
        onClick={() => void save()}
        className="min-h-10 rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)] disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save preferences"}
      </button>

      <div className="border-t border-[var(--border)] pt-4">
        <h3 className="text-sm font-semibold">Preview plan</h3>
        <p className="text-xs text-[var(--muted)]">
          Uses synced Canvas course and assignment IDs (not display names).
        </p>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <input
            placeholder="Course ID"
            value={previewAssignment.courseId}
            onChange={(e) => setPreviewAssignment((p) => ({ ...p, courseId: e.target.value }))}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
          <input
            placeholder="Assignment ID"
            value={previewAssignment.assignmentId}
            onChange={(e) => setPreviewAssignment((p) => ({ ...p, assignmentId: e.target.value }))}
            className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
          />
        </div>
        <button type="button" className="mt-2 text-sm underline" onClick={() => void runPreview()}>
          Preview reminder plan
        </button>
        {previewError ? <ApiErrorPanel error={previewError} /> : null}
        {preview ? (
          <div className="mt-3 rounded-lg border border-[var(--border)] p-3 text-sm">
            <p className="font-medium">{preview.title}</p>
            <p className="text-[var(--muted)]">{preview.summary}</p>
            <p className="mt-2 text-xs">Due {formatDueDate(preview.plan.dueAt)}</p>
            <ul className="mt-2 list-disc pl-5 text-xs">
              {preview.plan.reminders.map((r, i) => (
                <li key={i}>
                  {r.leadHours}h before — {formatDueDate(r.at)} ({r.status})
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
