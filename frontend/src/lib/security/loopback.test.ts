import { describe, expect, it } from "vitest";
import { isLoopbackHostHeader, isLoopbackOrigin } from "@/lib/security/loopback";

describe("isLoopbackHostHeader", () => {
  it.each(["localhost", "LOCALHOST:3001", "127.0.0.1:13117", "[::1]:3001", "[::1]"])(
    "accepts %s",
    (host) => expect(isLoopbackHostHeader(host)).toBe(true),
  );
  it.each([
    null,
    undefined,
    "",
    "   ",
    "attacker.example",
    "localhost.attacker.example",
    "127.0.0.1.attacker.example",
    "localhost:evil",
    "localhost:99999",
    "localhost:",
    "localhost@attacker.example",
    "localhost, attacker.example",
    "[::1",
    "0.0.0.0",
  ])("rejects %s", (host) => expect(isLoopbackHostHeader(host)).toBe(false));
});

describe("isLoopbackOrigin", () => {
  it.each([
    "http://localhost:3001",
    "http://127.0.0.1:13117",
    "https://localhost:3000",
    "http://[::1]:3001",
  ])("accepts %s", (origin) => expect(isLoopbackOrigin(origin)).toBe(true));
  it.each([
    "null",
    "https://attacker.example",
    "http://localhost.attacker.example",
    "http://localhost@attacker.example",
    "http://localhost:3001/extra",
    "http://localhost:3001?x=1",
    "ftp://localhost:3001",
    "file://",
    "javascript:alert(1)",
    "",
  ])("rejects %s", (origin) => expect(isLoopbackOrigin(origin)).toBe(false));
});
