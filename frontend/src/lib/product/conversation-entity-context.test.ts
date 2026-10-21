/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  activeAssignmentIdFromMessages,
  activeDocumentIdFromMessages,
  isFollowUpEntityPrompt,
  pickAssignmentForFollowUp,
} from "@/lib/product/conversation-entity-context";
import type { ChatMessage } from "@/lib/domain/types";

describe("conversation entity context", () => {
  it("detects follow-up prompts", () => {
    expect(isFollowUpEntityPrompt("when is it due")).toBe(true);
    expect(isFollowUpEntityPrompt("how do i do the individual report")).toBe(true);
    expect(isFollowUpEntityPrompt("what do i have due today")).toBe(false);
  });

  it("reads assignment id from recent deadline block", () => {
    const messages: ChatMessage[] = [
      {
        id: "a1",
        role: "assistant",
        createdAt: new Date().toISOString(),
        blocks: [
          {
            type: "deadlines",
            content: "next_week",
            assignments: [{ id: "asg-99", courseId: "c1", title: "Report", dueAt: null }],
          },
        ],
      },
    ];
    expect(activeAssignmentIdFromMessages(messages)).toBe("asg-99");
  });

  it("does not guess an assignment from a multi-item deadline block", () => {
    const messages: ChatMessage[] = [
      {
        id: "a1",
        role: "assistant",
        createdAt: new Date().toISOString(),
        blocks: [
          {
            type: "deadlines",
            assignments: [
              { id: "asg-1", courseId: "c1", title: "One", dueAt: null },
              { id: "asg-2", courseId: "c1", title: "Two", dueAt: null },
            ],
          },
        ],
      },
    ];
    expect(activeAssignmentIdFromMessages(messages)).toBeNull();
  });

  it("retains one grounded document id from recent evidence", () => {
    const messages: ChatMessage[] = [
      {
        id: "d1",
        role: "assistant",
        createdAt: new Date().toISOString(),
        blocks: [
          {
            type: "document_answer",
            sources: [
              {
                id: "source-1",
                provenance: {
                  courseId: "c1",
                  courseName: "Course",
                  documentId: "file-6",
                },
              },
            ],
          },
        ],
      },
    ];
    expect(activeDocumentIdFromMessages(messages)).toBe("file-6");
  });

  it("reuses prior assignment on pronoun follow-up", () => {
    const assignments = [
      { id: "a1", courseId: "c1", title: "Individual Report", dueAt: null },
      { id: "a2", courseId: "c1", title: "Team Sprint Plan", dueAt: null },
    ];
    const picked = pickAssignmentForFollowUp("when is it due", assignments, "a1");
    expect(picked?.id).toBe("a1");
  });
});
