/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { displayText } from "@/lib/utils/display-text";

describe("displayText", () => {
  it("rejects undefined and NaN", () => {
    expect(displayText(undefined, "—")).toBe("—");
    expect(displayText("undefined", "—")).toBe("—");
    expect(displayText(Number.NaN, "—")).toBe("—");
  });

  it("strips object tags", () => {
    expect(displayText("[object Object]", "empty")).toBe("empty");
  });
});
