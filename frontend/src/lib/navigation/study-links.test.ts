/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildStudyWorkspaceUrl, pickDefaultStudyCourseId } from "@/lib/navigation/study-links";

describe("study links", () => {
  it("picks first due course for continue studying", () => {
    expect(
      pickDefaultStudyCourseId(
        [{ id: "c3" }],
        [{ courseId: "c1" }],
        [{ courseId: "c2" }],
      ),
    ).toBe("c1");
    expect(pickDefaultStudyCourseId([], [], [])).toBeUndefined();
  });

  it("omits empty courseId from continue url", () => {
    expect(buildStudyWorkspaceUrl({ continueSession: true })).toBe("/study?continue=1");
  });
});
