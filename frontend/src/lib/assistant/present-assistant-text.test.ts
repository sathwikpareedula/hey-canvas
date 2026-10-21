/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  deadlineEmptyMessageFromHint,
  shouldHideAssistantTextBlock,
} from "@/lib/assistant/present-assistant-text";

describe("present-assistant-text", () => {
  it("hides synthetic course context echoes", () => {
    expect(
      shouldHideAssistantTextBlock(
        "I can help with: What is due tomorrow?. Course context: unresolved.",
      ),
    ).toBe(true);
  });

  it("keeps substantive answers", () => {
    expect(shouldHideAssistantTextBlock("Here are three ways to prepare for the midterm.")).toBe(
      false,
    );
  });

  it("maps deadline empty hints", () => {
    expect(deadlineEmptyMessageFromHint("tomorrow")).toBe("Nothing due tomorrow.");
    expect(deadlineEmptyMessageFromHint("next_week")).toBe("Nothing due next week.");
    expect(deadlineEmptyMessageFromHint("this_week")).toBe("Nothing due this week.");
  });
});
