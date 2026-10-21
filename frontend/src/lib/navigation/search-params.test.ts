/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { removeSearchParams } from "@/lib/navigation/search-params";

describe("removeSearchParams", () => {
  it("removes keys while preserving route and other params", () => {
    const url = removeSearchParams(
      "/",
      new URLSearchParams("courseId=c1&assignmentId=a1&prompt=hi"),
      ["assignmentId", "prompt"],
    );
    expect(url).toBe("/?courseId=c1");
  });
});
