/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { AssistantSseDecoder, parseSseFrame } from "@/lib/api/http/assistant-stream-parser";
import { mapBackendSsePayloadToTransportEvents } from "@/lib/api/http/assistant-adapters";

describe("assistant SSE parser", () => {
  it("parses a single frame", () => {
    const frame = parseSseFrame(
      'event: started\ndata: {"type":"started","session_id":"s1"}\n',
    );
    expect(frame?.event).toBe("started");
    expect(frame?.data.session_id).toBe("s1");
  });

  it("handles split chunks and UTF-8", () => {
    const decoder = new AssistantSseDecoder();
    const part1 = 'event: text_delta\ndata: {"type":"text_delta","text":"caf';
    const part2 = 'é"}\n\n';
    expect(decoder.push(part1)).toHaveLength(0);
    const events = decoder.push(part2);
    expect(events).toHaveLength(1);
    expect(events[0]?.data.text).toBe("café");
  });

  it("ignores malformed JSON frames", () => {
    expect(parseSseFrame("data: not-json\n")).toBeNull();
  });
});

describe("assistant SSE event mapping", () => {
  it("maps completed responses", () => {
    const events = mapBackendSsePayloadToTransportEvents("completed", {
      type: "completed",
      response: {
        status: "ok",
        blocks: [{ type: "text", text: "Hello" }],
      },
    });
    expect(events[0]?.type).toBe("complete");
  });

  it("maps block events with payload", () => {
    const events = mapBackendSsePayloadToTransportEvents("block", {
      type: "block",
      block_type: "deadline_group",
      payload: {
        assignments: [
          {
            canvas_assignment_id: "a1",
            canvas_course_id: "c1",
            name: "Quiz",
          },
        ],
      },
    });
    expect(events[0]?.type).toBe("block");
    if (events[0]?.type === "block") {
      expect(events[0].block.assignments?.[0]?.title).toBe("Quiz");
    }
  });

  it("maps provider errors", () => {
    const events = mapBackendSsePayloadToTransportEvents("error", {
      type: "error",
      text: "assistant provider failed: RuntimeError",
    });
    expect(events[0]?.type).toBe("error");
  });
});
