/**
 * @vitest-environment node
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchSystemReadiness } from "@/lib/api/http/local-ai-client";

describe("local AI client with an unreachable backend", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("treats a network failure as missing readiness data instead of rejecting", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    await expect(fetchSystemReadiness()).resolves.toBeNull();
  });

  it("still surfaces unexpected server errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 500 })),
    );
    await expect(fetchSystemReadiness()).rejects.toBeDefined();
  });
});
