"""Capture curated high-resolution portfolio screenshots for Hey Canvas V1.2.

Target directory: portfolio-assets/hey-canvas/
Target files:
1. 01-dashboard-desktop.png (1280x1050) - Primary Full-Stack project image
2. 02-ai-study-assistant.png (1280x950) - Primary AI/ML project image with Quiz 3 study plan and citations
3. 03-today-priorities.png (1280x1000) - Populated daily academic view
4. 04-deadline-calendar.png (1280x1150) - Calendar with a selected deadline
5. 05-course-materials.png (1280x1000) - Course materials and provenance
6. 06-mobile-view.png (390x844) - Mobile layout view
"""

import os
import sys
import time
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = os.environ.get("HEY_CANVAS_SCREENSHOT_BASE_URL", "http://localhost:3001")
DEMO_COURSE_ID = "synthetic-robotics"
OUTPUT_DIR = os.path.abspath("portfolio-assets/hey-canvas")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_driver(width=1280, height=900):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={width},{height}")
    opts.add_argument("--force-device-scale-factor=1")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    return driver

def open_demo_route(driver, path):
    """Open a route only after opting this isolated browser into completed setup."""
    driver.get(f"{BASE_URL}/startup")
    driver.execute_script(
        "window.localStorage.setItem('hey-canvas-onboarding-v1', "
        "JSON.stringify({version: 1, completed: true, currentStep: 'ready', "
        "updatedAt: new Date().toISOString()}));"
    )
    driver.get(f"{BASE_URL}{path}")
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    WebDriverWait(driver, 20).until(
        lambda current: "demo data" in current.find_element(By.TAG_NAME, "body").text.lower()
    )
    body = driver.find_element(By.TAG_NAME, "body").text
    if "278791" in body:
        raise RuntimeError("Refusing to capture a screenshot containing a known real course id")

def capture_all():
    print(f"Starting portfolio screenshot capture to {OUTPUT_DIR}...")
    
    # 1. Dashboard Desktop (1280x900)
    print("\n[1/6] Capturing 01-dashboard-desktop.png...")
    driver = create_driver(1280, 1050)
    try:
        open_demo_route(driver, "/dashboard")
        time.sleep(3)  # wait for data fetching and cards render
        out_path = os.path.join(OUTPUT_DIR, "01-dashboard-desktop.png")
        driver.save_screenshot(out_path)
        print(f"Saved: {out_path} ({os.path.getsize(out_path):,} bytes)")
    finally:
        driver.quit()

    # 2. AI Study Assistant with Two-Link Forward Kinematics Explanation (1280x1350)
    print("\n[2/6] Capturing 02-ai-study-assistant.png...")
    driver = create_driver(1280, 1350)
    try:
        prompt_text = "Can you explain forward kinematics for a two-link robotic arm using my course materials?"
        encoded_prompt = quote_plus(prompt_text)
        open_demo_route(driver, f"/?courseId={DEMO_COURSE_ID}&prompt={encoded_prompt}")
        print("Dispatched prompt to assistant, waiting for streaming response...")
        
        # Wait up to 35 seconds for assistant response to stream and stabilize
        start_t = time.time()
        for i in range(35):
            time.sleep(1)
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "forward kinematics" in body_text.casefold() and ("worked example" in body_text.casefold() or "two-link" in body_text.casefold() or "kinematics equations" in body_text.casefold()):
                print(f"Response detected after {time.time() - start_t:.1f}s")
                time.sleep(3)
                break
        
        # Ensure user prompt is visible at top of conversation
        driver.execute_script("""
            const allElements = Array.from(document.querySelectorAll('*'));
            const userMsg = allElements.find(el => 
                el.children.length === 0 && 
                el.textContent.includes('Can you explain forward kinematics')
            );
            if (userMsg) {
                userMsg.scrollIntoView({ behavior: 'instant', block: 'start' });
            }
        """)
        time.sleep(1)
        
        out_path = os.path.join(OUTPUT_DIR, "02-ai-study-assistant.png")
        driver.save_screenshot(out_path)
        print(f"Saved: {out_path} ({os.path.getsize(out_path):,} bytes)")
    finally:
        driver.quit()

    # 3. Today priorities (1280x1000)
    print("\n[3/6] Capturing 03-today-priorities.png...")
    driver = create_driver(1280, 1000)
    try:
        open_demo_route(driver, "/today")
        time.sleep(3)
        out_path = os.path.join(OUTPUT_DIR, "03-today-priorities.png")
        driver.save_screenshot(out_path)
        print(f"Saved: {out_path} ({os.path.getsize(out_path):,} bytes)")
    finally:
        driver.quit()

    # 4. Deadline Calendar (1280x900)
    print("\n[4/6] Capturing 04-deadline-calendar.png...")
    driver = create_driver(1280, 1150)
    try:
        open_demo_route(driver, "/calendar")
        time.sleep(3)
        deadline_days = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='assignment deadline']")
        populated = [
            item for item in deadline_days
            if not (item.get_attribute("aria-label") or "").split(":", 1)[-1].strip().startswith("0 ")
        ]
        if not populated:
            raise RuntimeError("Synthetic calendar has no populated deadline day")
        # Select the latest populated day so the detail panel demonstrates an
        # upcoming synthetic deadline rather than an already elapsed example.
        populated[-1].click()
        time.sleep(1)
        out_path = os.path.join(OUTPUT_DIR, "04-deadline-calendar.png")
        driver.save_screenshot(out_path)
        print(f"Saved: {out_path} ({os.path.getsize(out_path):,} bytes)")
    finally:
        driver.quit()

    # 5. Course materials and provenance (1280x1000)
    print("\n[5/6] Capturing 05-course-materials.png...")
    driver = create_driver(1280, 1000)
    try:
        open_demo_route(driver, f"/courses/{DEMO_COURSE_ID}")
        materials_tab = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@role='tab' and normalize-space()='Materials']"))
        )
        materials_tab.click()
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.ID, "course-panel-materials"))
        )
        time.sleep(2)
        out_path = os.path.join(OUTPUT_DIR, "05-course-materials.png")
        driver.save_screenshot(out_path)
        print(f"Saved: {out_path} ({os.path.getsize(out_path):,} bytes)")
    finally:
        driver.quit()

    # 6. Mobile View (390x844)
    print("\n[6/6] Capturing 06-mobile-view.png...")
    driver = create_driver(390, 844)
    try:
        open_demo_route(driver, "/dashboard")
        time.sleep(3)
        out_path = os.path.join(OUTPUT_DIR, "06-mobile-view.png")
        driver.save_screenshot(out_path)
        print(f"Saved: {out_path} ({os.path.getsize(out_path):,} bytes)")
    finally:
        driver.quit()

    print("\nAll 6 portfolio screenshots successfully captured!")

if __name__ == "__main__":
    capture_all()
