/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  bucketCoursesForFocus,
  suggestInitialFocusCourseIds,
  toggleFocusCourseId,
} from "@/lib/product/focus-courses";
import type { Course } from "@/lib/domain/types";

const catalog: Course[] = [
  { id: "1", name: "Machine Learning", term: "Fall 2026", code: "CSE 4309" },
  { id: "2", name: "Neural Networks", term: "Fall 2026", code: "CSE 4360" },
  { id: "3", name: "Senior Design", term: "Fall 2026", code: "CSE 4310" },
  { id: "4", name: "Intro 2019", term: "Fall 2019", code: "CSE 1101" },
  { id: "5", name: "Faculty Training Sandbox", term: "Fall 2026" },
  { id: "6", name: "Concur Travel", term: "Fall 2026" },
  { id: "7", name: "Undergraduate Advising", term: "Fall 2026" },
  { id: "8", name: "Math Placement", term: "Evergreen" },
];

describe("focus courses", () => {
  it("buckets likely current term courses", () => {
    const buckets = bucketCoursesForFocus(catalog);
    expect(buckets.likelyCurrent.map((c) => c.id)).toEqual(["1", "2", "3"]);
    expect(buckets.trainingOrResources.some((c) => c.id === "5")).toBe(true);
    expect(buckets.past.some((c) => c.id === "4")).toBe(true);
  });

  it("suggests initial focus ids from likely current", () => {
    const ids = suggestInitialFocusCourseIds(catalog, 4);
    expect(ids).toEqual(["1", "2", "3"]);
    expect(ids).not.toContain("6");
    expect(ids).not.toContain("7");
    expect(ids).not.toContain("8");
  });

  it("toggles focus membership", () => {
    expect(toggleFocusCourseId("1", [])).toEqual(["1"]);
    expect(toggleFocusCourseId("1", ["1", "2"])).toEqual(["2"]);
  });
});
