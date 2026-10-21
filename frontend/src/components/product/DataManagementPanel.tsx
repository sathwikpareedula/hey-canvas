"use client";

import { useState } from "react";
import { getProductSettingsApi } from "@/lib/api/product-settings-service";
import type { DataLifecycleAction } from "@/lib/domain/product-settings";
import { PRODUCT_STORAGE_KEYS } from "@/lib/product/storage-keys";

const ACTIONS: {
  action: DataLifecycleAction;
  title: string;
  description: string;
  confirmPhrase: string;
}[] = [
  {
    action: "clear_assistant_context",
    title: "Clear assistant context",
    description: "Removes in-browser assistant session pointers. Does not delete synced Canvas data.",
    confirmPhrase: "CLEAR ASSISTANT",
  },
  {
    action: "clear_study_sessions",
    title: "Clear study session pointers",
    description: "Forgets saved study session ids in this browser.",
    confirmPhrase: "CLEAR STUDY",
  },
  {
    action: "clear_practice_sessions",
    title: "Clear practice session pointers",
    description: "Forgets saved practice session ids in this browser.",
    confirmPhrase: "CLEAR PRACTICE",
  },
  {
    action: "clear_local_index",
    title: "Clear local product preferences cache",
    description: "Resets focus courses and AI preference cache in this browser. Server copy remains if synced.",
    confirmPhrase: "CLEAR CACHE",
  },
];

function clearBrowserPointers(action: DataLifecycleAction): void {
  if (typeof window === "undefined") return;
  if (action === "clear_assistant_context") {
    /* conversation is in-memory; user starts new chat */
  }
  if (action === "clear_study_sessions") {
    window.localStorage.removeItem("hey-canvas-study-session-id");
  }
  if (action === "clear_practice_sessions") {
    window.localStorage.removeItem("hey-canvas-practice-session-id");
  }
  if (action === "clear_local_index") {
    Object.values(PRODUCT_STORAGE_KEYS).forEach((k) => window.localStorage.removeItem(k));
  }
}

export function DataManagementPanel() {
  const [pending, setPending] = useState<DataLifecycleAction | null>(null);
  const [phrase, setPhrase] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const active = ACTIONS.find((a) => a.action === pending);

  const run = async () => {
    if (!active) return;
    if (phrase.trim() !== active.confirmPhrase) {
      setMessage("Confirmation phrase did not match.");
      return;
    }
    setBusy(true);
    setMessage(null);
    const api = getProductSettingsApi();
    const result = await api.executeDataLifecycle({
      action: active.action,
      confirmToken: "CONFIRM",
    });
    clearBrowserPointers(active.action);
    setMessage(result.ok ? result.message : result.message);
    setBusy(false);
    setPending(null);
    setPhrase("");
  };

  return (
    <section id="data-management" className="space-y-3 rounded-xl border border-[var(--border)] p-4 scroll-mt-20">
      <h2 className="text-sm font-semibold">Data management</h2>
      <p className="text-xs text-[var(--muted)]">
        Destructive actions require typing the confirmation phrase. Disconnecting Canvas is handled on
        your local Hey Canvas service — not in this browser.
      </p>
      <ul className="space-y-2">
        {ACTIONS.map((a) => (
          <li key={a.action} className="rounded-lg border border-[var(--border)] p-3">
            <p className="text-sm font-medium">{a.title}</p>
            <p className="text-xs text-[var(--muted)]">{a.description}</p>
            <button
              type="button"
              className="mt-2 text-sm text-[var(--accent)] underline"
              onClick={() => {
                setPending(a.action);
                setPhrase("");
                setMessage(null);
              }}
            >
              Manage
            </button>
          </li>
        ))}
      </ul>
      {active ? (
        <div
          className="rounded-lg border border-[var(--warn-border)] bg-[var(--warn-bg)] p-3"
          role="dialog"
          aria-labelledby="data-confirm-title"
        >
          <p id="data-confirm-title" className="text-sm font-medium">{active.title}</p>
          <p className="mt-1 text-xs">
            Type <strong>{active.confirmPhrase}</strong> to confirm.
          </p>
          <label className="mt-2 block text-xs">
            Confirmation
            <input
              className="mt-1 w-full rounded-md border border-[var(--border)] px-2 py-1"
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              autoComplete="off"
            />
          </label>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void run()}
              className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm text-[var(--accent-fg)] disabled:opacity-50"
            >
              Confirm
            </button>
            <button
              type="button"
              onClick={() => setPending(null)}
              className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}
      {message ? (
        <p className="text-sm text-[var(--muted)]" role="status">{message}</p>
      ) : null}
    </section>
  );
}
