"""Real-browser journeys against an ISOLATED synthetic stack (Playwright for Python).

Prerequisites (see docs/V12-OVERNIGHT-RELEASE-REPORT.md for the exact commands):
  pip install playwright && python -m playwright install chromium
  Backend  : disposable synthetic DB seeded with `academic-seed-demo`, port 18000
  Frontend : built with NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:18000 and
             NEXT_PUBLIC_ACADEMIC_API_MODE=http, served on port 13117.

Usage: python scripts/e2e/browser_journeys_v12.py [--out DIR] [--frontend URL] [--backend URL]
Never point this at a real Canvas database or the live V1.1 installation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

from playwright.async_api import Page, async_playwright

RESULTS: list[dict[str, Any]] = []
IGNORED_CONSOLE = (
    "Failed to decode downloaded font",  # sandbox uses mocked fonts
    "OTS parsing error",
    "Failed to load resource",  # HTTP failures are asserted per-URL below instead
)
EXPECTED_HTTP_FAILURES = (
    "/api/benchmarks/ollama/models",  # Ollama is intentionally absent
    "/api/product/disambiguation/resolve",  # 404 is handled by design (unresolved)
)
INJECTED_FAULT_MARKERS = ("ERR_CONNECTION_RESET", "ERR_FAILED")


def record(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append({"journey": name, "passed": passed, "detail": detail})
    print(("PASS" if passed else "FAIL"), name, detail)


async def finish_onboarding(page: Page, frontend: str) -> None:
    await page.goto(f"{frontend}/onboarding", wait_until="networkidle")
    if "onboarding" in page.url:
        started = page.get_by_role("button", name="Get started")
        if await started.count():
            await started.click()
            await page.get_by_role("button", name="Continue").click()
        await page.get_by_role("button", name="Finish setup").click()
        await page.wait_for_url("**/dashboard")
    await page.wait_for_load_state("networkidle")


async def send(page: Page, text: str) -> None:
    box = page.get_by_role("textbox", name="Message Hey Canvas")
    await box.fill(text)
    await box.press("Enter")


async def chat_idle(page: Page) -> bool:
    box = page.get_by_role("textbox", name="Message Hey Canvas")
    await box.fill("x")
    enabled = await page.get_by_role("button", name="Send").is_enabled()
    await box.fill("")
    return enabled and await box.is_enabled()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/e2e/shots")
    parser.add_argument("--frontend", default="http://127.0.0.1:13117")
    parser.add_argument("--backend", default="http://127.0.0.1:18000")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frontend: str = args.frontend

    import urllib.request

    assignments = json.load(urllib.request.urlopen(f"{args.backend}/api/assignments"))
    worksheet = next(a for a in assignments if a["name"] == "Kinematics Worksheet")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        console_problems: list[str] = []
        page_errors: list[str] = []
        page.on(
            "console",
            lambda m: console_problems.append(m.text[:200])
            if m.type == "error"
            and not any(i in m.text for i in (*IGNORED_CONSOLE, *INJECTED_FAULT_MARKERS))
            else None,
        )
        page.on("pageerror", lambda e: page_errors.append(str(e)[:200]))
        http_failures: list[str] = []
        page.on(
            "response",
            lambda r: http_failures.append(f"{r.status} {r.url}")
            if r.status >= 400 and not any(u in r.url for u in EXPECTED_HTTP_FAILURES)
            else None,
        )

        # 1. Onboarding -> dashboard
        await finish_onboarding(page, frontend)
        await page.wait_for_function(
            "() => document.querySelector('main')?.innerText.includes('Kinematics Worksheet')",
            timeout=15000,
        )
        body = await page.locator("main").inner_text()
        record("onboarding_to_dashboard", "dashboard" in page.url, page.url)
        await page.screenshot(path=str(out / "01-dashboard.png"))
        record("dashboard_shows_synthetic_deadline", "Kinematics Worksheet" in body)

        # 2. Navigation pages render fixture data, with no client crash.
        for path, expect in [
            ("/courses", "Synthetic Autonomous Robots"),
            ("/assignments", "Kinematics Worksheet"),
            ("/materials", "Synthetic Kinematics Notes"),
            ("/changes", None),
            ("/settings", None),
        ]:
            await page.goto(f"{frontend}{path}", wait_until="networkidle")
            text = await page.locator("main").inner_text()
            ok = (expect in text) if expect else len(text) > 20
            record(f"page_{path.strip('/')}", ok, "" if ok else text[:120])
            await page.screenshot(path=str(out / f"02-{path.strip('/')}.png"))

        # 3. Chat: deterministic deadline answer streams, controls recover.
        await page.goto(f"{frontend}/", wait_until="networkidle")
        await send(page, "What is due today?")
        await page.wait_for_function(
            "() => document.body.innerText.match(/CDT|CST|Nothing due|nothing is due|due today/i)",
            timeout=15000,
        )
        await page.wait_for_timeout(500)
        text = await page.locator("main").inner_text()
        record("chat_due_today_streams", bool(re.search(r"CDT|CST|due today|Nothing", text)))
        record("chat_controls_recover_after_answer", await chat_idle(page))
        await page.screenshot(path=str(out / "03-chat-due-today.png"))

        # 4. Course-scoped assignment points match the backend truth.
        await page.get_by_role("button", name="New conversation").click()
        await page.get_by_label("Course context").select_option(label="Synthetic Autonomous Robots")
        await send(page, "How many points is Kinematics Worksheet worth?")
        points = f"{worksheet['points_possible']:g}" if worksheet["points_possible"] else None
        try:
            await page.wait_for_function(
                "(p) => document.body.innerText.includes(p ?? 'does not list')",
                arg=points,
                timeout=15000,
            )
            record("chat_points_match_backend_truth", True, f"points={points}")
        except Exception as exc:
            record("chat_points_match_backend_truth", False, type(exc).__name__)
        await page.screenshot(path=str(out / "04-chat-points.png"))

        # 5. Stream that dies without a terminal event must not wedge the UI.
        await page.get_by_role("button", name="New conversation").click()

        async def truncated(route: Any) -> None:
            await route.fulfill(
                status=200,
                headers={"content-type": "text/event-stream"},
                body='event: started\ndata: {"type":"started"}\n\n',
            )

        await page.route("**/api/assistant/stream", truncated)
        await send(page, "What is due tomorrow?")
        await page.wait_for_timeout(2500)
        record("truncated_stream_recovers_controls", await chat_idle(page))
        await page.screenshot(path=str(out / "05-truncated-stream.png"))
        await page.unroute("**/api/assistant/stream")

        # 6. Aborted chat request (connection reset) must show an error, not crash.
        async def abort(route: Any) -> None:
            await route.abort("connectionreset")

        await page.route("**/api/assistant/stream", abort)
        await send(page, "When is Kinematics Worksheet due?")
        await page.wait_for_timeout(2500)
        record("aborted_stream_recovers_controls", await chat_idle(page))
        await page.unroute("**/api/assistant/stream")

        # 7. Disconnected backend: every API call fails; pages must still render.
        pre_fault_http_failure_count = len(http_failures)
        await page.route("**/api/**", abort)
        await page.goto(f"{frontend}/dashboard", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        text = await page.locator("body").inner_text()
        record("backend_down_dashboard_renders", len(text) > 40 and "Application error" not in text)
        await page.screenshot(path=str(out / "07-backend-down.png"))
        # HTTP errors produced while the test deliberately severs API traffic are
        # evidence of the injected condition, not unexpected product failures.
        del http_failures[pre_fault_http_failure_count:]
        await page.unroute("**/api/**")

        # 8. Keyboard navigation and Ctrl+K command palette.
        await page.goto(f"{frontend}/", wait_until="networkidle")
        await page.keyboard.press("Tab")
        focused = await page.evaluate("() => document.activeElement?.tagName")
        record("keyboard_tab_moves_focus", focused not in (None, "BODY"), str(focused))
        await page.keyboard.press("Control+k")
        await page.wait_for_timeout(400)
        dialog = await page.get_by_role("dialog").count()
        record("ctrl_k_opens_command_palette", dialog > 0)
        await page.keyboard.press("Escape")

        # 9. Mobile viewport: no horizontal overflow on key pages.
        await page.set_viewport_size({"width": 390, "height": 844})
        for path in ("/", "/dashboard", "/assignments", "/settings"):
            await page.goto(f"{frontend}{path}", wait_until="networkidle")
            overflow = await page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth"
            )
            record(f"mobile_no_horizontal_overflow{path or '/'}", overflow <= 1, f"overflow={overflow}")
            if path == "/":
                await page.screenshot(path=str(out / "09-mobile-chat.png"))

        record("no_uncaught_page_errors", not page_errors, "; ".join(page_errors[:3]))
        record("no_unexpected_http_failures", not http_failures, "; ".join(http_failures[:3]))
        record("no_unexpected_console_errors", not console_problems, "; ".join(console_problems[:3]))
        await browser.close()

    (out / "results.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    failed = [r for r in RESULTS if not r["passed"]]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} journeys passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
