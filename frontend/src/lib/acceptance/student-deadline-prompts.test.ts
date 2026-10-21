/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { matchDeadlineFastPath } from "@/lib/product/deadline-fast-path";

const NEXT = "next_week";
const THIS = "this_week";
const TODAY = "today";
const TOMORROW = "tomorrow";
const OVERDUE = "overdue";
const PRIORITIES = "priorities";

describe("student deadline prompts", () => {
  it("matches casual today and tomorrow phrasing", () => {
    expect(matchDeadlineFastPath("bro whats due")).toBe(TODAY);
    expect(matchDeadlineFastPath("what i got tmrw")).toBe(TOMORROW);
    expect(matchDeadlineFastPath("anything due tn")).toBe(TODAY);
    expect(matchDeadlineFastPath("what do i gotta do today")).toBe(TODAY);
    expect(matchDeadlineFastPath("do i have anything today")).toBe(TODAY);
  });

  it("matches week windows and corrections", () => {
    expect(matchDeadlineFastPath("anything next wk")).toBe(NEXT);
    expect(matchDeadlineFastPath("show next week's work")).toBe(NEXT);
    expect(matchDeadlineFastPath("i asked next week")).toBe(NEXT);
    expect(matchDeadlineFastPath("no, NEXT week")).toBe(NEXT);
    expect(matchDeadlineFastPath("what's due this week?")).toBe(THIS);
  });

  it("matches overdue and priority-style prompts", () => {
    expect(matchDeadlineFastPath("am i missing anything?")).toBe(OVERDUE);
    expect(matchDeadlineFastPath("what's most urgent?")).toBe(OVERDUE);
    expect(matchDeadlineFastPath("give me my priorities")).toBe(PRIORITIES);
    expect(matchDeadlineFastPath("which one should i do first")).toBe(PRIORITIES);
    expect(matchDeadlineFastPath("what should i work on tonight?")).toBe(PRIORITIES);
  });
});
