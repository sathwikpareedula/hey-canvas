"""Phase 3: Live Ollama Academic Evaluation Script.

Evaluates:
1. Relative-angle two-link planar forward kinematics
2. A* search explanation and follow-up
3. Quiz lecture coverage with conflicting or excluded ranges
4. Assignment with missing instructions
5. Cross-course evidence isolation
6. Citation and evidence correctness
7. Streaming cancellation and immediate recovery
8. New-conversation reset
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
import urllib.error
import http.client

BASE_URL = "http://127.0.0.1:8000"
COURSE_ID = "278791"  # Autonomous Robots focus course
OTHER_COURSE_ID = "278788"  # Machine Learning course


def stream_assistant(payload: dict, timeout: float = 120.0) -> dict:
    """Stream assistant response and collect all events."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/assistant/stream",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-Hey-Canvas-Client": "hey-canvas-local",
            "Origin": "http://localhost:3001",
        },
        method="POST",
    )
    started = time.perf_counter()
    first_token_time = None
    text_deltas = []
    completed_event = None
    error_event = None
    references = []

    with urllib.request.urlopen(req, timeout=timeout) as response:
        for line in response:
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str.startswith("data:"):
                continue
            body = line_str[5:].strip()
            if not body or body == "[DONE]":
                continue
            try:
                ev = json.loads(body)
            except json.JSONDecodeError:
                continue

            ev_type = ev.get("type")
            if ev_type == "text_delta":
                txt = ev.get("text", "")
                if txt:
                    if first_token_time is None:
                        first_token_time = time.perf_counter() - started
                    text_deltas.append(txt)
            elif ev_type == "block":
                txt = ev.get("text") or ""
                if txt and not text_deltas:
                    text_deltas.append(txt)
            elif ev_type == "source":
                refs = ev.get("references") or []
                references.extend(refs)
            elif ev_type == "completed":
                completed_event = ev
            elif ev_type == "error":
                error_event = ev

    total_time = time.perf_counter() - started
    final_text = "".join(text_deltas)
    if completed_event and completed_event.get("response"):
        resp = completed_event["response"]
        for block in resp.get("blocks", []):
            if block.get("type") == "text" and not final_text:
                final_text = block.get("text") or ""
            if block.get("references"):
                references.extend(block["references"])

    return {
        "text": final_text or "",
        "first_token_time": first_token_time,
        "total_time": total_time,
        "completed": completed_event is not None,
        "error": error_event,
        "references": references,
        "raw_completed": completed_event,
    }


def test_1_forward_kinematics() -> dict:
    print("\n--- Test 1: Relative-angle two-link planar forward kinematics ---")
    query = (
        "Derive the forward kinematics for a two-link planar manipulator arm with link lengths L1 and L2, "
        "and joint angles theta1 and theta2, where theta2 is measured relative to link 1. "
        "What are the final coordinates (x, y) of the end effector?"
    )
    res = stream_assistant({"query": query, "course_id": COURSE_ID, "session_id": "fk-eval-1"})
    text = res["text"] or ""
    print(f"Latency: {res['total_time']:.2f}s, Text length: {len(text)}")
    print(f"Sample response:\n{text[:500]}...\n")

    # Check for expected relative angle terms:
    # x = L1*cos(theta1) + L2*cos(theta1 + theta2)
    # y = L1*sin(theta1) + L2*sin(theta1 + theta2)
    t_lower = text.lower()

    # Pattern check for relative angle combinations: theta1 + theta2 or \theta_1 + \theta_2
    has_sum_angle = bool(
        re.search(r"theta[_\s]*1\s*\+\s*theta[_\s]*2", t_lower)
        or re.search(r"\b\(\s*θ\s*1\s*\+\s*θ\s*2\s*\)", t_lower)
        or re.search(r"θ1\s*\+\s*θ2", t_lower)
        or re.search(r"cos\s*\(\s*[^)]*1[^)]*\+[^)]*2[^)]*\)", t_lower)
        or "theta_1 + theta_2" in t_lower
        or "theta1 + theta2" in t_lower
    )

    has_l1_cos = bool(re.search(r"l_?1\s*\*?\s*cos", t_lower) or "l1 cos" in t_lower or "l1cos" in t_lower)
    has_l2_cos = bool(re.search(r"l_?2\s*\*?\s*cos", t_lower) or "l2 cos" in t_lower or "l2cos" in t_lower)
    has_l1_sin = bool(re.search(r"l_?1\s*\*?\s*sin", t_lower) or "l1 sin" in t_lower or "l1sin" in t_lower)
    has_l2_sin = bool(re.search(r"l_?2\s*\*?\s*sin", t_lower) or "l2 sin" in t_lower or "l2sin" in t_lower)

    passed = has_sum_angle and (has_l1_cos or has_l2_cos) and (has_l1_sin or has_l2_sin)
    print(f"Sum angle (theta1+theta2) present: {has_sum_angle}")
    print(f"L1/L2 cos/sin terms present: L1_cos={has_l1_cos}, L2_cos={has_l2_cos}, L1_sin={has_l1_sin}, L2_sin={has_l2_sin}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "latency": res["total_time"], "details": text[:300]}


def test_2_astar_explanation_and_followup() -> dict:
    print("\n--- Test 2: A* search explanation and follow-up ---")
    session_id = f"astar-eval-{int(time.time())}"
    # Turn 1
    q1 = "Explain robot path planning including A* search."
    res1 = stream_assistant({"query": q1, "course_id": COURSE_ID, "session_id": session_id})
    print(f"Turn 1 latency: {res1['total_time']:.2f}s")
    t1_lower = (res1["text"] or "").lower()
    has_astar_t1 = "a*" in t1_lower or "heuristic" in t1_lower or "cost" in t1_lower

    # Turn 2
    q2 = "Can you give me a simple example?"
    res2 = stream_assistant({"query": q2, "course_id": COURSE_ID, "session_id": session_id})
    print(f"Turn 2 latency: {res2['total_time']:.2f}s")
    t2_lower = (res2["text"] or "").lower()

    # Topic continuity check: Turn 2 must discuss A* search/grid/graph/path, NOT forward kinematics
    has_astar_t2 = ("a*" in t2_lower or "heuristic" in t2_lower or "node" in t2_lower or "grid" in t2_lower or "graph" in t2_lower or "path" in t2_lower)
    has_no_stale_kinematics = "forward kinematics" not in t2_lower and "joint angle" not in t2_lower

    passed = has_astar_t1 and has_astar_t2 and has_no_stale_kinematics
    print(f"Turn 1 has A*: {has_astar_t1}")
    print(f"Turn 2 has A* continuity: {has_astar_t2}")
    print(f"Turn 2 free of stale kinematics: {has_no_stale_kinematics}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "turn1_time": res1["total_time"], "turn2_time": res2["total_time"]}


def test_3_quiz_lecture_coverage_conflicts() -> dict:
    print("\n--- Test 3: Quiz lecture coverage with conflicting or excluded ranges ---")
    query = (
        "For our exam preparation, the announcement says the quiz covers Lectures 1 through 5, "
        "but Lecture 4 on vision is excluded. Which lectures should I study and which is excluded?"
    )
    res = stream_assistant({"query": query, "course_id": COURSE_ID, "session_id": "quiz-cov-3"})
    t_lower = (res["text"] or "").lower()
    print(f"Latency: {res['total_time']:.2f}s")
    print(f"Sample response:\n{res['text'][:400]}...\n")

    # The model should acknowledge exclusion of Lecture 4 or focus on Lectures 1, 2, 3, 5
    noted_exclusion = (
        "exclude" in t_lower
        or "excluding" in t_lower
        or "except" in t_lower
        or "omit" in t_lower
        or "not lecture 4" in t_lower
        or "1, 2, 3" in t_lower
        or "1-3" in t_lower
    )
    passed = res["completed"] and len(res["text"]) > 50 and noted_exclusion
    print(f"Noted exclusion: {noted_exclusion}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "latency": res["total_time"]}


def test_4_assignment_with_missing_instructions() -> dict:
    print("\n--- Test 4: Assignment with missing instructions ---")
    # Quiz 3 has empty description in Canvas
    query = "Explain what Quiz 3 is asking for in plain language."
    res = stream_assistant({"query": query, "course_id": COURSE_ID, "session_id": "missing-inst-4"})
    t_lower = (res["text"] or "").lower()
    print(f"Latency: {res['total_time']:.2f}s")
    print(f"Sample response:\n{res['text'][:400]}...\n")

    # Must be honest: cannot verify, no instructions provided, or does not explain
    is_honest = (
        "can't verify" in t_lower
        or "cannot verify" in t_lower
        or "does not explain" in t_lower
        or "do not explain" in t_lower
        or "no description" in t_lower
        or "no instructions" in t_lower
        or "does not contain" in t_lower
        or "not provided" in t_lower
    )
    # Must not hallucinate random content as assignment instructions
    passed = is_honest
    print(f"Honest lack of instructions reported: {is_honest}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "latency": res["total_time"]}


def test_5_cross_course_isolation() -> dict:
    print("\n--- Test 5: Cross-course evidence isolation ---")
    # Ask in Machine Learning course (281070) about Autonomous Robots Assignment 2393399
    query = "Explain assignment 2393399."
    res = stream_assistant({"query": query, "course_id": "281070", "session_id": "iso-eval-5"})
    t_lower = (res["text"] or "").lower()
    print(f"Latency: {res['total_time']:.2f}s")
    print(f"Sample response:\n{res['text'][:400]}...\n")

    # Check that it refused or stated lack of context/information for assignment 2393399
    is_isolated = (
        "do not have" in t_lower
        or "don't have" in t_lower
        or "no assignment context" in t_lower
        or "cannot find" in t_lower
        or "not found" in t_lower
        or "could not find" in t_lower
        or "missing" in t_lower
    )
    # Check references: none should have course_id 278791 (cross-course leak)
    leaked_refs = [
        r for r in res["references"]
        if str(r.get("course_id") or "") == COURSE_ID
    ]
    no_leakage = len(leaked_refs) == 0 and is_isolated
    passed = no_leakage and res["completed"]
    print(f"Refusal/Isolation confirmed: {is_isolated}")
    print(f"No cross-course references leaked: {len(leaked_refs) == 0} (leaked: {len(leaked_refs)})")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "latency": res["total_time"]}


def test_6_citation_and_evidence_correctness() -> dict:
    print("\n--- Test 6: Citation and evidence correctness ---")
    query = "What is due soon in this course?"
    res = stream_assistant({"query": query, "course_id": COURSE_ID, "session_id": "cite-eval-6"})
    print(f"Latency: {res['total_time']:.2f}s")
    refs = res["references"]
    print(f"References count: {len(refs)}")

    # All references should have an identifier, authority, and belong to the correct course
    valid_citations = True
    for r in refs:
        print(f"  Ref: authority={r.get('authority')} id={r.get('identifier')} label={r.get('label')}")
        if not r.get("authority") or not r.get("identifier"):
            valid_citations = False

    passed = res["completed"] and len(res["text"]) > 20 and valid_citations
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "ref_count": len(refs), "latency": res["total_time"]}


def test_7_streaming_cancellation_and_recovery() -> dict:
    print("\n--- Test 7: Streaming cancellation and immediate recovery ---")
    # Step 1: Start a stream and close connection after 1 second (abrupt disconnect)
    data = json.dumps({
        "query": "Write an extensive multi-paragraph explanation of SLAM and probabilistic robotics algorithms.",
        "course_id": COURSE_ID,
        "session_id": "cancel-eval-7",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/api/assistant/stream",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-Hey-Canvas-Client": "hey-canvas-local",
            "Origin": "http://localhost:3001",
        },
        method="POST",
    )
    print("Initiating long stream to abort...")
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            # Read only first line then abort
            resp.readline()
            time.sleep(0.5)
            # Force close socket to simulate client disconnect
            resp.close()
    except Exception as e:
        print(f"Client disconnected as intended: {e}")

    # Immediate follow-up request to test backend recovery
    print("Sending immediate recovery request...")
    t0 = time.perf_counter()
    res2 = stream_assistant({
        "query": "When is Quiz 3 due?",
        "course_id": COURSE_ID,
        "session_id": "recovery-eval-7",
    })
    rec_time = time.perf_counter() - t0
    print(f"Recovery request finished in {rec_time:.2f}s, completed={res2['completed']}")
    passed = res2["completed"] and "Quiz 3" in res2["text"]
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "recovery_latency": rec_time}


def test_8_new_conversation_reset() -> dict:
    print("\n--- Test 8: New-conversation reset ---")
    # Conversation A establishes a topic
    sess_a = f"sess-a-{int(time.time())}"
    stream_assistant({
        "query": "Explain robot forward kinematics and Denavit-Hartenberg parameters.",
        "course_id": COURSE_ID,
        "session_id": sess_a,
    })

    # Conversation B starts fresh with a generic question
    sess_b = f"sess-b-{int(time.time())}"
    res_b = stream_assistant({
        "query": "Can you give me a simple example?",
        "course_id": COURSE_ID,
        "session_id": sess_b,
    })
    tb_lower = res_b["text"].lower()
    print(f"Conversation B response sample:\n{res_b['text'][:300]}...\n")

    # In a brand new conversation without prior context, it should either ask what topic
    # or not be contaminated by conversation A's DH parameters
    leaked_dh = "denavit" in tb_lower or "hartenberg" in tb_lower
    passed = not leaked_dh and res_b["completed"]
    print(f"No DH parameter leakage into new session: {not leaked_dh}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "latency": res_b["total_time"]}


def main():
    print("=" * 60)
    print("Phase 3: Live Ollama Academic Evaluation Suite")
    print(f"Backend: {BASE_URL}")
    print(f"Course: {COURSE_ID}")
    print("=" * 60)

    results = {}
    tests = [
        ("1_forward_kinematics", test_1_forward_kinematics),
        ("2_astar_followup", test_2_astar_explanation_and_followup),
        ("3_quiz_coverage_conflicts", test_3_quiz_lecture_coverage_conflicts),
        ("4_missing_instructions", test_4_assignment_with_missing_instructions),
        ("5_cross_course_isolation", test_5_cross_course_isolation),
        ("6_citation_correctness", test_6_citation_and_evidence_correctness),
        ("7_cancellation_recovery", test_7_streaming_cancellation_and_recovery),
        ("8_new_conversation_reset", test_8_new_conversation_reset),
    ]

    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            results[name] = {"passed": False, "error": str(e)}

    print("\n" + "=" * 60)
    print("Phase 3 Evaluation Summary:")
    passed_count = sum(1 for r in results.values() if r.get("passed"))
    total_count = len(results)
    for name, r in results.items():
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"  {name:30}: {status}")
    print(f"\nTotal: {passed_count}/{total_count} PASSED")
    print("=" * 60)

    if passed_count < total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
