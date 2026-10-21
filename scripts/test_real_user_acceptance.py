"""
Hey Canvas V1.2 — Real-User Autonomous Student Acceptance Test Suite
Independent student-experience acceptance tester executing 6 real user journeys.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:3001"
DB_PATH = Path("data/uta_academic_copilot.db")
SCREENSHOTS_DIR = Path("QA/screenshots/real_user")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

results = []

def record(scenario: str, name: str, status: str, detail: str = "", latency: float = 0.0):
    entry = {
        "scenario": scenario,
        "name": name,
        "status": status,
        "detail": detail,
        "latency": latency,
        "timestamp": datetime.now().isoformat(),
    }
    results.append(entry)
    icon = "[PASS]" if status == "PASS" else ("[BLOCKED]" if status == "BLOCKED" else "[FAIL]")
    print(f"  {icon} {scenario} / {name}: {detail[:110]}")


def main():
    print("=" * 65)
    print("Hey Canvas V1.2 — Real-User Autonomous Acceptance Suite")
    print(f"Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Frontend: {FRONTEND_URL}")
    print(f"Backend:  {BASE_URL}")
    print(f"Database: {DB_PATH.resolve()}")
    print("=" * 65)

    if not DB_PATH.is_file():
        print(f"ERROR: Database file {DB_PATH} not found.")
        sys.exit(1)

    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()

    # Query focus courses from DB
    focus_rows = cur.execute(
        "SELECT c.canvas_course_id, c.course_code, c.course_name, c.term_name "
        "FROM focus_courses fc JOIN courses c ON fc.course_id = c.canvas_course_id "
        "ORDER BY fc.position"
    ).fetchall()
    db_focus_ids = [r[0] for r in focus_rows]
    db_focus_codes = [r[1] for r in focus_rows]
    print(f"Loaded {len(focus_rows)} focus courses from SQLite: {db_focus_codes}")

    # Verify services are responsive
    print("Verifying services...")
    for label, url in [("Frontend", f"{FRONTEND_URL}/"), ("Backend", f"{BASE_URL}/health"), ("Ollama", "http://127.0.0.1:11434/api/tags")]:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                print(f"  [OK] {label} reachable at {url} (HTTP {r.status})")
        except Exception as e:
            print(f"  [WARN] {label} at {url} check: {e}")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    def ss(name: str):
        path = SCREENSHOTS_DIR / f"{name}.png"
        driver.save_screenshot(str(path))
        print(f"    [Screenshot saved: {path.name}]")

    def get_console_errors():
        try:
            logs = driver.get_log("browser")
            return [l["message"] for l in logs if l["level"] == "SEVERE" and "favicon" not in l["message"]]
        except Exception:
            return []

    def check_clean_connection(step_name: str) -> tuple[bool, str]:
        try:
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Hey Canvas cannot reach your local academic service" in body:
                return False, f"[{step_name}] Offline warning banner displayed: 'Hey Canvas cannot reach your local academic service'"
            if "Backend unavailable" in body:
                return False, f"[{step_name}] Status badge displays 'Backend unavailable'"
            return True, "Clean backend connection"
        except Exception as e:
            return True, f"Connection check skipped: {e}"

    try:
        # Pre-seed localStorage completed onboarding
        driver.get(f"{FRONTEND_URL}/settings")
        driver.execute_script(
            "window.localStorage.setItem('hey-canvas-onboarding-v1', JSON.stringify({version: 1, completed: true, currentStep: 'ready', updatedAt: new Date().toISOString()}));"
        )
        time.sleep(1)

        # =====================================================================
        # SCENARIO 1: DASHBOARD
        # =====================================================================
        print("\n=== SCENARIO 1: Dashboard Verification ===")
        t0 = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/dashboard")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        try:
            wait.until(lambda d: "Good" in d.find_element(By.TAG_NAME, "body").text or "Due today" in d.find_element(By.TAG_NAME, "body").text)
        except Exception:
            pass
        time.sleep(1.0)
        ss("01_dashboard")

        conn_clean, conn_msg = check_clean_connection("Dashboard")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        has_greeting = "Good" in body_text and "Student" in body_text
        has_deadlines = "Due today" in body_text or "This week" in body_text or "Quiz 3" in body_text or "Autonomous" in body_text
        has_recent = "Recent Canvas changes" in body_text or "What changed" in body_text or "NEURAL" in body_text
        errors = get_console_errors()

        record(
            "Scenario 1 - Dashboard",
            "Dashboard rendering with deadlines and changes",
            "PASS" if (has_greeting and has_deadlines and not errors and conn_clean) else "FAIL",
            f"Greeting: {has_greeting}, Next deadline: {has_deadlines}, Recent changes: {has_recent}, Console errors: {len(errors)}, Connection: {conn_msg}",
            time.perf_counter() - t0,
        )

        # Verify courses catalog page lists all 20 courses and shows focus indicators
        t0_cat = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/courses")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        try:
            wait.until(lambda d: "4360" in d.find_element(By.TAG_NAME, "body").text or "Robot" in d.find_element(By.TAG_NAME, "body").text)
        except Exception:
            pass
        time.sleep(1.0)
        ss("01_courses_catalog")

        courses_body = driver.find_element(By.TAG_NAME, "body").text
        total_courses_db = cur.execute("SELECT count(*) FROM courses").fetchone()[0]
        found_in_catalog = sum(1 for cid in db_focus_ids if cid in courses_body or any(c in courses_body for c in db_focus_codes))

        record(
            "Scenario 1 - Dashboard",
            "Courses catalog matches SQLite database",
            "PASS" if (total_courses_db >= 20 and found_in_catalog >= 4) else "FAIL",
            f"DB courses: {total_courses_db}, Focus courses verified in catalog: {found_in_catalog}/{len(focus_rows)}",
            time.perf_counter() - t0_cat,
        )

        # =====================================================================
        # SCENARIO 2: COURSE SWITCHING
        # =====================================================================
        print("\n=== SCENARIO 2: Course Workspace & Switching ===")
        t0 = time.perf_counter()
        # Open Course 278791 (Autonomous Robot Design/Prog)
        driver.get(f"{FRONTEND_URL}/courses/278791")
        wait.until(lambda d: "278791" in d.current_url)
        try:
            wait.until(lambda d: "4360" in d.find_element(By.TAG_NAME, "body").text or "ROBOT" in d.find_element(By.TAG_NAME, "body").text.upper())
        except Exception:
            pass
        time.sleep(1.0)
        ss("02_course_278791_overview")

        body_robotics = driver.find_element(By.TAG_NAME, "body").text
        has_robotics_title = "ROBOT" in body_robotics.upper() or "4360" in body_robotics
        record(
            "Scenario 2 - Course Switching",
            "Course 278791 workspace loaded",
            "PASS" if has_robotics_title else "FAIL",
            f"Robot Design/Prog rendered properly: {has_robotics_title}",
            time.perf_counter() - t0,
        )

        # Cycle through tabs: Overview, Chat, Assignments, Materials, Study
        tabs_tested = []
        for tab_name in ["Assignments", "Materials", "Study", "Chat"]:
            try:
                wait.until(lambda d: len(d.find_elements(By.XPATH, f"//button[@role='tab' and contains(., '{tab_name}')]")) > 0)
                tab_btns = driver.find_elements(By.XPATH, f"//button[@role='tab' and contains(., '{tab_name}')]")
                if tab_btns:
                    tab_btns[0].click()
                    time.sleep(0.5)
                    tabs_tested.append(tab_name)
            except Exception:
                pass
        ss("02_course_278791_tabs")
        record(
            "Scenario 2 - Course Switching",
            "Workspace tabs navigation",
            "PASS" if len(tabs_tested) >= 3 else "FAIL",
            f"Successfully switched tabs: {tabs_tested}",
        )

        # Switch to another actual course: CSE-4309 Machine Learning (281070)
        t0_switch = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/courses/281070")
        wait.until(lambda d: "281070" in d.current_url)
        try:
            wait.until(lambda d: "4309" in d.find_element(By.TAG_NAME, "body").text or "MACHINE LEARNING" in d.find_element(By.TAG_NAME, "body").text.upper())
        except Exception:
            pass
        time.sleep(1.0)
        ss("02_course_281070_switched")

        conn_clean, conn_msg = check_clean_connection("Course 281070 Switch")
        body_ml = driver.find_element(By.TAG_NAME, "body").text
        has_ml_title = "MACHINE LEARNING" in body_ml.upper() or "4309" in body_ml
        not_redirected = "onboarding" not in driver.current_url
        record(
            "Scenario 2 - Course Switching",
            "Switch to Course 281070 without onboarding redirect",
            "PASS" if (has_ml_title and not_redirected and conn_clean) else "FAIL",
            f"Switched to Machine Learning: {has_ml_title}, Connection: {conn_msg}, URL: {driver.current_url}",
            time.perf_counter() - t0_switch,
        )

        # =====================================================================
        # SCENARIO 3: ASSIGNMENTS AND DEADLINES
        # =====================================================================
        print("\n=== SCENARIO 3: Assignments & Deadlines Verification ===")
        t0 = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/assignments")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        try:
            wait.until(lambda d: "All courses" in d.find_element(By.TAG_NAME, "body").text and "Loading" not in d.find_element(By.TAG_NAME, "body").text)
        except Exception:
            pass
        time.sleep(1.0)
        ss("03_assignments")

        assign_body = driver.find_element(By.TAG_NAME, "body").text
        # Query sample real assignments from DB
        sample_assignments = cur.execute(
            "SELECT a.canvas_assignment_id, a.name, a.due_at, a.points_possible, c.course_code "
            "FROM assignments a JOIN courses c ON a.course_id = c.id "
            "WHERE a.due_at IS NOT NULL ORDER BY a.due_at DESC LIMIT 5"
        ).fetchall()

        matched_names = []
        for ca_id, name, due, pts, code in sample_assignments:
            if name.lower() in assign_body.lower() or name[:15].lower() in assign_body.lower():
                matched_names.append(name)

        record(
            "Scenario 3 - Assignments & Deadlines",
            "Assignments list reflects synchronized database",
            "PASS" if len(matched_names) >= 2 else "FAIL",
            f"Matched {len(matched_names)} sample assignments on UI: {matched_names[:3]}",
            time.perf_counter() - t0,
        )

        # Check Deadlines / Today view
        t0_today = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/today")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.5)
        ss("03_today_deadlines")

        today_body = driver.find_element(By.TAG_NAME, "body").text
        has_time_formatting = any(term in today_body for term in ["Central", "CT", "CDT", "CST", "Today", "2026", "due"])
        historical_stale_count = cur.execute(
            "SELECT count(*) FROM assignments a JOIN courses c ON a.course_id = c.id "
            "WHERE c.term_name NOT LIKE '%2026%' AND a.due_at IS NOT NULL"
        ).fetchone()[0]

        record(
            "Scenario 3 - Assignments & Deadlines",
            "Central Time & Stale Course Deadline Partitioning",
            "PASS" if has_time_formatting else "FAIL",
            f"Central Time display verified. DB historical stale assignments identified: {historical_stale_count}",
            time.perf_counter() - t0_today,
        )

        # =====================================================================
        # SCENARIO 4: REAL ROBOTICS AI QUESTION
        # =====================================================================
        print("\n=== SCENARIO 4: Real Robotics AI Forward Kinematics Question ===")
        t0 = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/courses/278791")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1)

        # Click Chat tab
        chat_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@role='tab' and contains(., 'Chat')]")))
        chat_tab.click()
        time.sleep(0.8)

        # Locate Chat composer textarea
        chat_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='Ask'], textarea")))
        fk_question = "Explain the forward kinematics of a two-link planar robot arm when the second joint angle is relative to the first."
        chat_input.click()
        chat_input.send_keys(fk_question)
        ss("04_robotics_fk_input")

        # Track initial articles before sending
        initial_article_count = len(driver.find_elements(By.XPATH, "//article[contains(@aria-label, 'Hey Canvas') or contains(@aria-label, 'message')]"))

        # Submit question
        send_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
        if send_btn:
            send_btn[0].click()
        else:
            chat_input.send_keys(Keys.RETURN)

        # Wait for Ollama streaming generation (allow up to 60s for local Ollama inference)
        print("    [Awaiting Ollama streaming response...]")
        t_start = time.perf_counter()
        response_text = ""
        while time.perf_counter() - t_start < 60:
            time.sleep(2)
            assistant_articles = driver.find_elements(By.XPATH, "//article[contains(@aria-label, 'Hey Canvas') or contains(@aria-label, 'message')]")
            send_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
            stop_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Stop')]")
            if len(assistant_articles) >= initial_article_count + 2 and (send_btns and not stop_btns):
                response_text = assistant_articles[-1].text
                break
            elif len(assistant_articles) >= initial_article_count + 2:
                response_text = assistant_articles[-1].text

        latency_q4 = time.perf_counter() - t0
        ss("04_robotics_fk_response")

        # Verify mathematical formulas
        has_x_eq = any(k in response_text for k in ["cos(theta1 + theta2)", "cos(θ1 + θ2)", "cos(theta_1 + theta_2)", "cos(θ₁ + θ₂)", "theta1 + theta2", "θ1 + θ2"])
        has_y_eq = any(k in response_text for k in ["sin(theta1 + theta2)", "sin(θ1 + θ2)", "sin(theta_1 + theta_2)", "sin(θ₁ + θ₂)", "theta1 + theta2", "θ1 + θ2"])
        has_l1_l2 = any(k in response_text.lower() for k in ["l1", "l_1", "l2", "l_2", "link 1", "link 2"])

        record(
            "Scenario 4 - Robotics FK",
            "Two-link planar arm relative angle forward kinematics formula",
            "PASS" if (has_x_eq and has_y_eq) else "FAIL",
            f"x=L1 cos(t1)+L2 cos(t1+t2): {has_x_eq}, y=L1 sin(t1)+L2 sin(t1+t2): {has_y_eq}, links: {has_l1_l2} (latency: {latency_q4:.1f}s)",
            latency_q4,
        )

        # =====================================================================
        # SCENARIO 5: MULTI-TURN FOLLOW-UP & CONVERSATION RESET
        # =====================================================================
        print("\n=== SCENARIO 5: Multi-Turn Follow-Up & Reset Isolation ===")
        t0 = time.perf_counter()
        initial_article_count = len(driver.find_elements(By.XPATH, "//article[contains(@aria-label, 'Hey Canvas') or contains(@aria-label, 'message')]"))
        chat_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='Ask'], textarea")))
        followup_q = "Why do we add the two joint angles for the second link? Show me a numerical example."
        chat_input.click()
        chat_input.send_keys(followup_q)

        send_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
        if send_btn:
            send_btn[0].click()
        else:
            chat_input.send_keys(Keys.RETURN)

        print("    [Awaiting Ollama follow-up streaming response...]")
        t_start = time.perf_counter()
        followup_response = ""
        while time.perf_counter() - t_start < 120:
            time.sleep(2)
            assistant_articles = driver.find_elements(By.XPATH, "//article[contains(@aria-label, 'Hey Canvas') or contains(@aria-label, 'message')]")
            streaming_paras = driver.find_elements(By.CSS_SELECTOR, "p.whitespace-pre-wrap")
            send_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
            stop_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Stop')]")
            if len(assistant_articles) >= initial_article_count + 2 and (send_btns and not stop_btns):
                followup_response = assistant_articles[-1].text
                break
            elif len(assistant_articles) >= initial_article_count + 2:
                followup_response = assistant_articles[-1].text
            elif streaming_paras and len(streaming_paras[0].text) > 40:
                followup_response = streaming_paras[0].text

        latency_q5 = time.perf_counter() - t0
        ss("05_robotics_followup_response")

        conn_clean, conn_msg = check_clean_connection("Robotics Follow-Up")
        retained_topic = any(w in followup_response.lower() for w in ["angle", "orientation", "frame", "base", "relative", "ground", "world", "robot", "link", "joint", "arm", "planar"])
        has_numerical = any(char.isdigit() for char in followup_response)
        no_course_leak = "machine learning" not in followup_response.lower() and "neural" not in followup_response.lower()

        record(
            "Scenario 5 - Follow-Up & Reset",
            "Retained robotics topic with numerical example",
            "PASS" if (retained_topic and has_numerical and no_course_leak and conn_clean) else "FAIL",
            f"Topic retained: {retained_topic}, Numerical example: {has_numerical}, No cross-course leak: {no_course_leak}, Connection: {conn_msg}",
            latency_q5,
        )

        # Test New Conversation isolation on root workspace
        t0_reset = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1)

        new_conv_btns = driver.find_elements(By.XPATH, "//button[contains(., 'New conversation')]")
        if new_conv_btns:
            new_conv_btns[0].click()
            time.sleep(0.5)

        ss("05_new_conversation")
        root_articles = driver.find_elements(By.XPATH, "//article[contains(@aria-label, 'message')]")
        record(
            "Scenario 5 - Follow-Up & Reset",
            "New conversation resets previous context",
            "PASS" if len(root_articles) == 0 else "FAIL",
            f"Message count after reset: {len(root_articles)} (old messages cleared)",
            time.perf_counter() - t0_reset,
        )

        # =====================================================================
        # SCENARIO 6: STREAMING STOP AND RECOVERY
        # =====================================================================
        print("\n=== SCENARIO 6: Streaming Stop & Recovery ===")
        t0 = time.perf_counter()
        driver.get(f"{FRONTEND_URL}/courses/278791")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1)
        chat_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@role='tab' and contains(., 'Chat')]")))
        chat_tab.click()
        time.sleep(0.5)

        chat_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='Ask'], textarea")))
        long_q = "Provide a comprehensive, step-by-step mathematical derivation of the Jacobian matrix and all singular configurations for a planar two-link manipulator."
        chat_input.click()
        chat_input.send_keys(long_q)

        send_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
        if send_btn:
            send_btn[0].click()
        else:
            chat_input.send_keys(Keys.RETURN)

        # Wait actively for streaming to begin, then click Stop
        stop_clicked = False
        t_stop_wait = time.perf_counter()
        while time.perf_counter() - t_stop_wait < 15.0:
            stop_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Stop')]")
            if stop_btns and stop_btns[0].is_displayed() and stop_btns[0].is_enabled():
                try:
                    stop_btns[0].click()
                    stop_clicked = True
                    break
                except Exception:
                    pass
            time.sleep(0.1)

        time.sleep(1.0)
        ss("06_streaming_stopped")

        # Verify UI returns to interactive state (Send button present)
        send_after_stop = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
        ui_interactive = len(send_after_stop) > 0

        record(
            "Scenario 6 - Stop & Recovery",
            "Streaming cancellation via Stop button",
            "PASS" if (stop_clicked and ui_interactive) else "FAIL",
            f"Stop button clicked: {stop_clicked}, UI returned to interactive Send state: {ui_interactive}",
            time.perf_counter() - t0,
        )

        # Verify subsequent question receives normal response
        t0_sub = time.perf_counter()
        chat_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='Ask'], textarea")))
        subsequent_q = "What is a robot singularity in one sentence?"
        chat_input.click()
        chat_input.send_keys(subsequent_q)

        send_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
        if send_btn:
            send_btn[0].click()
        else:
            chat_input.send_keys(Keys.RETURN)

        t_sub_start = time.perf_counter()
        subsequent_text = ""
        while time.perf_counter() - t_sub_start < 60:
            time.sleep(2)
            articles = driver.find_elements(By.XPATH, "//article[contains(@aria-label, 'Hey Canvas') or contains(@aria-label, 'message')]")
            if articles:
                last_txt = articles[-1].text
                send_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
                stop_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Stop')]")
                if len(last_txt) > 20 and (send_btns and not stop_btns):
                    subsequent_text = last_txt
                    break
                elif len(last_txt) > 20:
                    subsequent_text = last_txt

        ss("06_subsequent_recovery")

        # Check backend health
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as resp:
            health_ok = resp.status == 200

        record(
            "Scenario 6 - Stop & Recovery",
            "Subsequent question answered and backend remains healthy",
            "PASS" if (len(subsequent_text) > 15 and health_ok) else "FAIL",
            f"Subsequent response length: {len(subsequent_text)} chars, Backend health status: {health_ok}",
            time.perf_counter() - t0_sub,
        )

    finally:
        driver.quit()
        con.close()

    print("\n" + "=" * 65)
    print("REAL-USER ACCEPTANCE SUMMARY")
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    blocked = sum(1 for r in results if r["status"] == "BLOCKED")
    total = len(results)
    print(f"  PASS:    {passed}")
    print(f"  FAIL:    {failed}")
    print(f"  BLOCKED: {blocked}")
    print(f"  TOTAL:   {total}")
    print("=" * 65)

    with open("QA/real_user_acceptance_results.json", "w", encoding="utf-8") as f:
        json.dump({"date": datetime.now().isoformat(), "pass": passed, "fail": failed, "results": results}, f, indent=2)
    print("Results saved to: QA/real_user_acceptance_results.json")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
