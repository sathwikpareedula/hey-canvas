/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";

/** Keyboard routing logic mirrored for unit testing. */
function moveActiveIndex(current: number, direction: "up" | "down", max: number) {
  if (direction === "down") return Math.min(current + 1, max);
  return Math.max(current - 1, 0);
}

describe("command palette navigation", () => {
  it("clamps arrow navigation", () => {
    expect(moveActiveIndex(0, "up", 5)).toBe(0);
    expect(moveActiveIndex(5, "down", 5)).toBe(5);
    expect(moveActiveIndex(2, "down", 5)).toBe(3);
  });
});
