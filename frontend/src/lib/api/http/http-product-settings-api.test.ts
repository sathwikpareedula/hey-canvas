/**
 * @vitest-environment node
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HttpProductSettingsApi } from "@/lib/api/http/http-product-settings-api";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("HttpProductSettingsApi canonical routes", () => {
  const previousBase = process.env.NEXT_PUBLIC_API_BASE_URL;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (previousBase === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
    else process.env.NEXT_PUBLIC_API_BASE_URL = previousBase;
  });

  it("loads focus courses and privacy from their canonical resources", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([{ course_id: "9007199254740993" }]))
      .mockResolvedValueOnce(
        jsonResponse({ mode: "LOCAL_ONLY", updated_at: "2026-10-02T12:00:00Z" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const settings = await new HttpProductSettingsApi().getSettings();

    expect(settings?.focusCourseIds).toEqual(["9007199254740993"]);
    expect(settings?.aiProcessingMode).toBe("local");
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([
      "http://127.0.0.1:8000/api/focus-courses",
      "http://127.0.0.1:8000/api/privacy",
    ]);
  });

  it("writes focus and privacy settings without the obsolete product facade", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})));
    vi.stubGlobal("fetch", fetchMock);

    await new HttpProductSettingsApi().saveSettings({
      version: 1,
      focusCourseIds: ["course-1"],
      termHint: null,
      aiProcessingMode: "cloud",
      localModelTier: "recommended",
      privacyCloudOptInAcknowledged: true,
      updatedAt: "2026-10-02T12:00:00Z",
    });

    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([
      "http://127.0.0.1:8000/api/focus-courses",
      "http://127.0.0.1:8000/api/privacy",
    ]);
    expect(fetchMock.mock.calls.every((call) => !String(call[0]).includes("/api/product/"))).toBe(
      true,
    );
  });
});
