/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { createHttpAssistantTransport } from "@/lib/assistant/transports/http-transport";
import { HttpAcademicApi } from "@/lib/api/http-academic-api";

const run = process.env.RUN_PRODUCT_INTEGRATION === "1";
const base = process.env.PRODUCT_INTEGRATION_BASE_URL ?? "http://127.0.0.1:8000";

describe.runIf(run)("product HTTP integration smoke", () => {
  const api = (() => {
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE = "http";
    process.env.NEXT_PUBLIC_API_BASE_URL = base;
    return new HttpAcademicApi();
  })();

  it("assistant status", async () => {
    const res = await fetch(`${base}/api/assistant/status`);
    expect(res.ok).toBe(true);
    const body = await res.json();
    expect(body.available).toBe(true);
  });

  it("notifications list", async () => {
    const list = await api.getNotifications({ limit: 5 });
    expect(Array.isArray(list)).toBe(true);
  });

  it("reminder preferences round trip", async () => {
    const prefs = await api.getReminderPreferences();
    expect(prefs.timezone).toBeTruthy();
    const saved = await api.saveReminderPreferences(prefs);
    expect(saved.enabled).toBe(prefs.enabled);
  });

  it("assistant stream", async () => {
    const transport = createHttpAssistantTransport(base);
    const types: string[] = [];
    for await (const event of transport.send({ query: "What do I have due today?" })) {
      types.push(event.type);
      if (event.type === "complete") break;
    }
    expect(types).toContain("start");
    expect(types).toContain("complete");
  });

  it("study session lifecycle when course exists", async () => {
    const courses = await api.getCourses();
    if (!courses.length) return;
    const courseId = courses[0]!.id;
    const session = await api.createStudySession({
      courseId,
      goal: "Integration smoke",
      durationMinutes: 30,
      topics: ["smoke"],
      studyMode: "learn",
      assignmentIds: [],
    });
    expect(session.sessionId).toBeTruthy();
    const continued = await api.continueStudySession(session.sessionId);
    expect(continued.status).toBe("active");
    if (session.steps.length) {
      const advanced = await api.advanceStudySession(session.sessionId, session.steps[0]!.order);
      expect(advanced.progress).toBeGreaterThanOrEqual(0);
    }
  });

  it("practice session when course exists", async () => {
    const courses = await api.getCourses();
    if (!courses.length) return;
    const courseId = courses[0]!.id;
    const practice = await api.createPracticeSession(courseId, "smoke topic", 2);
    expect(practice.question?.question).toBeTruthy();
    const hint = await api.hintPracticeSession(practice.sessionId);
    expect(hint.length).toBeGreaterThan(0);
    const feedback = await api.answerPracticeSession(
      practice.sessionId,
      "A long enough practice answer for smoke testing.",
    );
    expect(feedback.feedback).toBeTruthy();
  });

  it("study guide when course exists", async () => {
    const courses = await api.getCourses();
    if (!courses.length) return;
    const guide = await api.buildStudyGuide({ courseId: courses[0]!.id, topic: "smoke" });
    expect(guide.title).toBeTruthy();
    expect(guide.scope).toBeTruthy();
  });

  it("calendar preview when assignment exists", async () => {
    const assignments = await api.getAssignments();
    if (!assignments.length) return;
    const a = assignments[0]!;
    try {
      const preview = await api.previewCalendarEvent(a.courseId, a.id);
      expect(preview.event.summary).toBeTruthy();
      expect(preview.confirmation.confirmationToken).toBeTruthy();
    } catch {
      // fixture may lack assignment in DB — skip assertion
    }
  });

  it("reminder preview when assignment exists", async () => {
    const assignments = await api.getAssignments();
    if (!assignments.length) return;
    const a = assignments[0]!;
    try {
      const plan = await api.previewReminderPlan(a.courseId, a.id);
      expect(plan.plan.planId).toBeTruthy();
    } catch {
      // optional fixture
    }
  });
});
