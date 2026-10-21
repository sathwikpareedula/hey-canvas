/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { messageFromHttpErrorBody } from "@/lib/api/http/parse-api-error";

describe("parse-api-error", () => {
  it("reads FastAPI detail string", () => {
    expect(messageFromHttpErrorBody(409, '{"detail":"study session not found"}')).toBe(
      "study session not found",
    );
  });

  it("hides traceback-like detail", () => {
    const msg = messageFromHttpErrorBody(500, '{"detail":"Traceback (most recent call last)"}');
    expect(msg).toBe("Something went wrong. Try again.");
  });
});
