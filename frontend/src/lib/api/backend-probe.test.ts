/**
 * @vitest-environment node
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { probeBackendConnection } from "@/lib/api/backend-probe";

describe("probeBackendConnection", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("returns mock in explicit mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_ACADEMIC_API_MODE", "mock");
    await expect(probeBackendConnection()).resolves.toBe("mock");
  });

  it("probes HTTP backend in default personal mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_ACADEMIC_API_MODE", "");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      }),
    );
    await expect(probeBackendConnection()).resolves.toBe("connected");
  });

  it("reports a healthy HTTP backend", async () => {
    vi.stubEnv("NEXT_PUBLIC_ACADEMIC_API_MODE", "http");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      }),
    );

    await expect(probeBackendConnection()).resolves.toBe("connected");
  });

  it("reports an unavailable backend for failed or malformed health responses", async () => {
    vi.stubEnv("NEXT_PUBLIC_ACADEMIC_API_MODE", "http");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({}) })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ status: "degraded" }),
        }),
    );

    await expect(probeBackendConnection()).resolves.toBe("unavailable");
    await expect(probeBackendConnection()).resolves.toBe("unavailable");
  });
});
