/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { NAV_ITEMS } from "@/components/layout/nav";

const APP_ROOT = join(process.cwd(), "src", "app");

function pageExistsForHref(href: string): boolean {
  if (href === "/") {
    return existsSync(join(APP_ROOT, "(app)", "page.tsx"));
  }
  const segments = href.replace(/^\//, "").split("/").filter(Boolean);
  const appPath = join(APP_ROOT, "(app)", ...segments, "page.tsx");
  if (existsSync(appPath)) return true;
  const dynamic = join(APP_ROOT, "(app)", ...segments.slice(0, -1), `[${segments.at(-1)}]`, "page.tsx");
  return existsSync(dynamic);
}

describe("app routes (source)", () => {
  it("every primary nav href maps to a page module", () => {
    for (const item of NAV_ITEMS) {
      expect(pageExistsForHref(item.href), `missing page for ${item.href}`).toBe(true);
    }
  });

  it("startup route exists outside app shell", () => {
    expect(
      existsSync(join(APP_ROOT, "(startup)", "startup", "page.tsx")),
    ).toBe(true);
  });

  it("launcher waits on /startup before browser open", () => {
    const launcher = join(process.cwd(), "..", "launcher", "windows", "Start-HeyCanvas.ps1");
    const source = readFileSync(launcher, "utf8");
    const readiness = "Wait-HeyCanvasStartup";
    const browser = "Start-Process $startupUrl";
    const marker = "Test-HeyCanvasStartupPage";
    expect(source.indexOf(marker)).toBeGreaterThan(-1);
    expect(source.indexOf(readiness)).toBeGreaterThan(-1);
    expect(source.indexOf(browser)).toBeGreaterThan(source.indexOf(readiness));
  });
});
