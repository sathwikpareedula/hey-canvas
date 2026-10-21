# Hey Canvas V1.2 — LinkedIn Post, Resume Bullets & Recruiter Guide

**Author:** Sathwik Pareedula  
**Project:** Hey Canvas (UTA Academic Copilot V1.2)  
**Repository:** [github.com/sathwikpareedula/hey-canvas](https://github.com/sathwikpareedula/hey-canvas)  

---

## 1. LinkedIn Announcement Post (Copy & Paste Ready)

```markdown
🚀 Excited to share a project I've been engineering: Hey Canvas (V1.2) — a local-first, privacy-preserving academic copilot built specifically for university coursework.

As a computer science student, my coursework was constantly scattered across Canvas LMS dashboards, syllabus PDFs, lecture slides, and discussion announcements. When students use commercial cloud chatbots for homework or study planning, two issues arise:
1. Academic Hallucination: Generic LLMs lack exact course syllabus context and hallucinate due dates and exam weightings.
2. Data Privacy: Uploading university lecture files and personal grades to third-party cloud APIs poses privacy concerns and FERPA risks.

I wanted an assistant that solved both problems by running 100% locally on the student's machine.

💡 Key Engineering Highlights:
1️⃣ Context-Aware Course Grounding: Ask questions scoped to a specific class (e.g. CSE 4360: Autonomous Robots). The copilot retrieves answers directly from synced syllabi, announcements, and module documents with verified citations.
2️⃣ Deterministic Fast-Path Routing: When you ask "What's due this month?", the query bypasses the LLM entirely. A deterministic SQLite engine resolves dates, points, and course structure in <1.3s with zero hallucination.
3️⃣ 100% Local On-Device AI: Powered by Llama 3.2 (3B) running locally via Ollama over loopback (127.0.0.1). Zero cloud telemetry, zero API subscription costs.
4️⃣ Resilient Stream Cancellation: Built an asynchronous concurrency shield (asyncio.shield) and threading barrier in FastAPI that eliminates database session race conditions when a user closes a tab mid-stream, terminating sockets in 0.30ms.
5️⃣ Managed Local Storage: Centralized storage panel in Next.js to monitor disk consumption, preview course documents, and clean temporary caches safely without risking database integrity.

🛠️ The Tech Stack:
• Frontend: Next.js 16 (Turbopack), React 19, TypeScript, Tailwind CSS
• Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite 3
• Local AI: Ollama running llama3.2:3b (GGUF Q4_K_M)
• Testing & QA: 310 Vitest tests (100% pass), Strict Mypy clean across 219 files, 40-case academic benchmarks

Honest Engineering Boundaries: On standard laptop CPUs, local 3B model generation averages ~4 tokens/sec with a first-token latency of ~3.75s. Course documents are prepared on-demand to respect student disk budgets rather than bulk-downloading gigabytes on startup.

Check out the architecture diagrams, benchmarks, and codebase on GitHub:
👉 https://github.com/sathwikpareedula/hey-canvas

#SoftwareEngineering #FullStack #Python #FastAPI #Nextjs #React #TypeScript #LocalAI #Ollama #SystemDesign #OpenSource
```

---

## 2. 30-Second Recruiter Pitch (For Phone Screenings & Intros)

> *"Hey Canvas is a full-stack, local-first academic copilot I built to solve course material fragmentation for university students. It synchronizes Canvas LMS course materials—syllabi, announcements, and modules—and provides an intelligent study assistant powered by a local 3B LLM running on the device via Ollama. 
> 
> What makes the engineering unique is its bifurcated architecture: high-stakes academic questions like deadlines and point totals route deterministically through an optimized SQLite engine in under 1.3 seconds to guarantee zero hallucinations, while conceptual study questions are augmented with course evidence and answered locally without any external cloud API calls. I also solved complex asynchronous streaming race conditions in FastAPI to ensure sub-millisecond tab cancellation without database session corruption."*

---

## 3. Resume Bullet Points

### Single-Line Summary (Ideal for Projects section header or compact resumes)
- **Hey Canvas (UTA Academic Copilot):** Built a local-first academic copilot using Next.js 16 (React 19), FastAPI, SQLite, and Ollama (`llama3.2:3b`), combining deterministic deadline routing (<1.3s) with course-grounded RAG study assistance and 100% local loopback privacy.

---

### Track A: Software Engineering & Full-Stack Systems Focus
- **Architected and built Hey Canvas**, a local-first academic platform integrating **FastAPI, Next.js 16 (React 19), SQLite, and Ollama (`llama3.2:3b`)** to deliver course-scoped study support with 100% on-device privacy.
- **Engineered an asynchronous concurrency shield** using `asyncio.shield` and thread barriers, eliminating critical SQLAlchemy session race conditions during client stream cancellations and achieving **0.30 ms** socket disconnect latency.
- **Developed a deterministic fast-path routing engine** that resolves calendar deadlines, grades, and course structure directly from SQLite in **<1.3s**, completely preventing LLM hallucinations for mission-critical schedules.
- **Implemented a managed storage subsystem** with REST inspection endpoints and an interactive React management panel, enabling per-course file inventory audits and safe cache cleanup while protecting database integrity.
- **Established rigorous automated quality gates**, achieving **100% pass rates across 310 frontend Vitest unit tests**, zero errors in strict Mypy across 219 Python source files, and automated end-to-end browser journeys.

---

### Track B: AI/ML Engineering & RAG Systems Focus
- **Engineered an on-device Retrieval-Augmented Generation (RAG) system** deploying quantized **Llama 3.2 (3B)** via Ollama on local loopback, generating syllabus-grounded study plans and practice problems with transparent source citations.
- **Designed an on-demand document ingestion pipeline** utilizing PyMuPDF and python-docx to parse, clean, and index course files lazily, minimizing disk utilization and startup latency on consumer hardware.
- **Evaluated local LLM performance and safety**, empirically measuring Time to First Token (**TTFT of 3.75s** on CPU), verifying prompt injection defenses against DAN jailbreaks, and achieving an **81.8% pass rate** across 22 live local inference scenarios.
- **Architected a bifurcated query dispatcher** separating deterministic factual queries (dates, policies) from generative tutoring, ensuring zero false deadline claims while maintaining responsive pedagogical explanations.

---

## 4. Technical Interview Deep Dives

### Topic 1: The FastAPI SSE Cancellation Race Condition
**Interviewer:** *"Can you describe a technically difficult concurrency bug you encountered and how you debugged and fixed it?"*  
**Your Answer:**
> "In FastAPI, when a client closes a Server-Sent Events (SSE) connection (such as closing the browser tab or aborting a generation), FastAPI immediately cancels the request handler's asyncio task. 
> 
> In our early implementation, this triggered an unraisable SQLAlchemy exception. The reason was that our assistant pipeline used a background worker thread to retrieve course evidence from SQLite while the main async loop streamed tokens. When the task was cancelled, FastAPI immediately began tearing down the request-scoped database dependency, closing the database session while the worker thread was still actively executing a query on it.
> 
> To fix this, we implemented an `asyncio.shield` wrap around the initial retrieval step and introduced a threading event barrier called `setup_finished`. When a hard cancellation is detected, the cancellation handler waits on `setup_finished` before cancelling the response stream. This guarantees the database read transaction is cleanly committed and closed before teardown, while the downstream Ollama HTTP streaming socket is immediately aborted in 0.30 milliseconds."

---

### Topic 2: Why Local AI Over Cloud APIs?
**Interviewer:** *"Why didn't you just call OpenAI's GPT-4 or Anthropic's Claude API?"*  
**Your Answer:**
> "There were three decisive reasons:
> 1. **Academic Privacy & FERPA:** Students' academic records—including specific grades, attendance, and unpublished exam review materials—should not be transmitted to commercial third-party cloud models without explicit institutional consent.
> 2. **Operational Cost & Availability:** University students shouldn't have to pay monthly subscription fees or run out of API credits during finals week. A local model runs indefinitely and offline.
> 3. **Engineering Challenge:** Building with an on-device model forced us to optimize prompt compaction, context windows, and lazy document indexing. We also recognized that 3B models should not be trusted for arithmetic or calendar math, which drove the architectural decision to build a deterministic SQLite fast-path for schedules, reserving the LLM for pedagogical tutoring."
