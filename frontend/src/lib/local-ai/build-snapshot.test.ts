/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { resolveInstalledModelMatch } from "@/lib/local-ai/build-snapshot";

describe("resolveInstalledModelMatch", () => {
  it("keeps full tag when backend reports short name", () => {
    expect(resolveInstalledModelMatch("llama3.2", ["llama3.2:3b"])).toBe("llama3.2:3b");
  });
});
