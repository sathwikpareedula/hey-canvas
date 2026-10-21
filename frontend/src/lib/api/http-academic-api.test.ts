/**
 * @vitest-environment node
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { HttpAcademicApi } from "@/lib/api/http-academic-api";
import { AcademicApiError } from "@/lib/api/errors";

describe("HttpAcademicApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("throws on non-2xx without mock fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }),
    );
    const api = new HttpAcademicApi();
    await expect(api.getCourses()).rejects.toBeInstanceOf(AcademicApiError);
  });

  it("throws on network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const api = new HttpAcademicApi();
    await expect(api.getCourses()).rejects.toMatchObject({ kind: "network" });
  });

  it("returns null when sync run is not found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
    );
    const api = new HttpAcademicApi();
    await expect(api.getSyncRun(999)).resolves.toBeNull();
  });

  it("searches documents without mock fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => [
            {
              canvas_course_id: "c-1",
              course_code: "EE",
              course_name: "Robotics",
              term_name: null,
            },
          ],
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => [
          {
            canvas_file_id: "f-1",
            display_name: "Doc",
            filename: "d.pdf",
            unit_type: "page",
            unit_index: 0,
            page_number: 1,
            slide_number: null,
            heading: null,
            snippet: "hello",
            score: 1,
            source_sha256: "sha",
            is_stale: false,
            references: [
              {
                canvas_course_id: "c-1",
                canvas_module_id: "m",
                canvas_module_item_id: "i",
                module_name: null,
                item_title: null,
              },
            ],
          },
        ],
        }),
    );
    const api = new HttpAcademicApi();
    const hits = await api.searchDocuments({ query: "hello" });
    expect(hits[0].documentId).toBe("f-1");
  });

  it("throws malformed when courses response is not an array", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ not: "array" }),
      }),
    );
    const api = new HttpAcademicApi();
    await expect(api.getCourses()).rejects.toMatchObject({ kind: "malformed" });
  });

  it("maps persisted course modules and their items", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [
        {
          canvas_module_id: "m-1",
          canvas_course_id: "c-1",
          name: "Week 1",
          position: 1,
          items: [
            {
              canvas_module_item_id: "i-1",
              canvas_module_id: "m-1",
              canvas_course_id: "c-1",
              title: "Lecture 1",
              item_type: "File",
              position: 2,
            },
          ],
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = new HttpAcademicApi();

    await expect(api.getModules("c-1")).resolves.toEqual([
      { id: "m-1", courseId: "c-1", name: "Week 1", position: 1 },
    ]);
    await expect(api.getModuleItems("c-1")).resolves.toEqual([
      {
        id: "i-1",
        moduleId: "m-1",
        courseId: "c-1",
        title: "Lecture 1",
        type: "File",
        position: 2,
      },
    ]);
  });
});
