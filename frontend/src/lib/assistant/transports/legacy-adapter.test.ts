/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { mapLegacyStreamEvent } from "@/lib/assistant/transports/legacy-adapter";

describe("mapLegacyStreamEvent", () => {
  it("maps status events to activity labels", () => {
    const events = mapLegacyStreamEvent({ type: "status", status: "thinking" });
    expect(events).toEqual([{ type: "activity", message: "Preparing explanation…" }]);
  });

  it("maps text deltas", () => {
    const events = mapLegacyStreamEvent({ type: "text_delta", delta: "Hi" });
    expect(events).toEqual([{ type: "text_delta", delta: "Hi" }]);
  });
});
