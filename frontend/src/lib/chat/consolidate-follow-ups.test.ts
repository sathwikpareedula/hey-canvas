/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { consolidateFollowUps } from "@/lib/chat/consolidate-follow-ups";

describe("consolidateFollowUps", () => {
  it("deduplicates follow-up suggestions", () => {
    expect(
      consolidateFollowUps([
        { type: "text", content: "a", followUps: ["More?"] },
        { type: "warning", content: "b", followUps: ["More?"] },
      ]),
    ).toEqual(["More?"]);
  });
});
