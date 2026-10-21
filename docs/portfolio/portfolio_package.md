# Hey Canvas (UTA Academic Copilot V1.2) — Portfolio Case Study & Package

**Author:** Sathwik Pareedula  
**Project:** Hey Canvas / UTA Academic Copilot  
**Repository:** [github.com/sathwikpareedula/hey-canvas](https://github.com/sathwikpareedula/hey-canvas)  
**Target Roles:** Full-Stack AI Engineer, Systems Software Engineer, Backend Engineer  

---

## 1. Executive Summary (65 words)

**Hey Canvas** is an autonomous, privacy-preserving academic copilot that integrates university Canvas LMS coursework with on-device local AI. Built with **Next.js 16 (React 19)**, **FastAPI (Python 3.12)**, **SQLite**, and **Ollama (`llama3.2:3b`)**, it combines a deterministic fast-path engine for hallucination-free deadlines with course-scoped RAG retrieval across syllabi, announcements, and modules. Operating entirely over loopback (`127.0.0.1`), it delivers zero-telemetry academic support with sub-millisecond cancellation safety.

---

## 2. In-Depth Technical Case Study

### The Problem
Undergraduate computer science coursework is fragmented across disconnected Canvas dashboards, disparate syllabus PDFs, discussion announcements, and lecture modules. When students turn to commercial cloud AI chatbots for study assistance, two critical failures occur:
1. **Academic Hallucinations:** Generic LLMs lack exact course syllabus context and frequently hallucinate due dates, assignment weights, and grading policies.
2. **Data Privacy & Academic Integrity Risks:** Uploading proprietary lecture notes, unreleased exam reviews, and personal grade records to external cloud APIs compromises privacy and violates FERPA/university data stewardship guidelines.

### The Approach
To solve this, Hey Canvas was engineered as a **local-first, privacy-preserving copilot**:
- **Bifurcated Routing:** Decouples factual academic scheduling from generative pedagogical tutoring. Inquiries regarding deadlines, points, and course structure route through a deterministic SQLite query engine (<1.3s response time), completely eliminating LLM hallucinations for mission-critical dates.
- **Course-Scoped RAG:** Course questions are strictly grounded using course-isolated vector and keyword retrieval across parsed syllabi, lecture slides, and professor announcements.
- **100% On-Device Inference:** Generative answers are synthesized locally using quantized `llama3.2:3b` via an Ollama daemon running on local loopback (`127.0.0.1`), ensuring zero outbound data egress.

### System Architecture
The application follows a resilient three-tier local architecture:
1. **Presentation Layer:** Next.js 16 with React 19, TypeScript, and Tailwind CSS. Utilizes Server-Sent Events (SSE) for token streaming, custom skeletons for layout stability, and responsive views down to 390px mobile viewports.
2. **Application Core:** FastAPI running on Python 3.12. Features an intent classifier, on-demand document extractor (PDF/DOCX), managed storage controller, and thread-safe streaming orchestrator.
3. **Data & AI Layer:** SQLite 3 for transactional Canvas mirrors, an on-disk course knowledge repository with directory traversal protection, and an Ollama LLM runtime.

### Key Engineering Challenges & Solutions

#### Challenge 1: SSE Cancellation Race Condition & Database Session Corruption
*Problem:* When students navigate away or close the browser tab during an active SSE stream, FastAPI triggers immediate task cancellation. In standard implementations, FastAPI tears down the request-scoped SQLAlchemy session while the background thread is still reading course context, causing unraisable database exceptions and thread leaks.  
*Solution:* Engineered an asynchronous concurrency shield (`asyncio.shield`) coupled with a thread synchronization barrier (`setup_finished`). The runner defers task aborts until the database session has cleanly exited its read transaction, then terminates the downstream Ollama HTTP socket in **0.30 ms** with zero database corruption.

#### Challenge 2: On-Demand Course Ingestion vs. Consumer Disk Budgets
*Problem:* Downloading and indexing every course file across 20 enrolled semesters consumes excessive disk storage and causes multi-minute startup delays.  
*Solution:* Developed a lazy, on-demand document preparation pipeline. The system synchronizes lightweight Canvas metadata instantly, prepares full text indices only when a course or document is queried, invalidates stale materials via ETag checks, and exposes a managed storage API (`/api/storage/*`) with user-facing cache cleanup tools.

### Security, Safety & Privacy Guarantees
- **Strict Read-Only Enforcement:** All Canvas LMS interactions are read-only HTTP GET requests; mutating actions (e.g., submitting assignments, modifying grades) are architecturally excluded.
- **Local Network Boundary:** All internal HTTP, SSE, and Ollama sockets bind exclusively to `127.0.0.1`. Cross-Origin Resource Sharing (CORS) explicitly rejects non-loopback origins.
- **Path Traversal Protection:** The managed storage engine sanitizes and resolves all file paths against an immutable data root, strictly prohibiting deletion or access to parent directories or the primary SQLite database.

### Quantitative Results & Verification Metrics
- **Automated Frontend Test Suite:** 310 / 310 tests passing across 87 Vitest suites (100% pass rate).
- **Backend Type Safety:** Clean strict Mypy across all 219 Python source files (`0 errors`); 100% clean Ruff linting.
- **Inference Latency:** Warm Time to First Token (TTFT) of **3.75s** on laptop CPU; socket disconnect teardown latency of **0.30 ms**.
- **Empirical LLM Benchmarks:** Evaluated against 22 live on-device inference scenarios (81.8% pass rate on local 3B model) and 40 deterministic academic test cases.

### Current Status
Hey Canvas V1.2 is a verified, fully functioning local release candidate on Windows 11, currently under an intentional release freeze to preserve reproducible benchmark artifacts and demonstration assets.

---

## 3. Technology Stack Matrix

| Layer | Technologies Used | Key Responsibilities |
|---|---|---|
| **Frontend** | Next.js 16 (Turbopack), React 19, TypeScript, Tailwind CSS, Lucide Icons | Responsive UI, SSE streaming consumers, voice synthesis/recognition, storage management panel |
| **Backend API** | Python 3.12, FastAPI, Pydantic V2, Uvicorn, Asyncio | REST endpoints, SSE stream orchestration, intent routing, concurrency shield |
| **Data & ORM** | SQLite 3, SQLAlchemy 2.0, Alembic migrations | Course catalog, assignments, syllabi, announcements, module items, conversation history |
| **Local AI Runtime** | Ollama, Llama 3.2 3B Instruct (GGUF Q4_K_M) | Local loopback generative tutor, grounded study guide generation, practice problem solver |
| **Document Processing** | PyMuPDF, python-docx, Beautiful Soup 4 | Syllabus and lecture slide text extraction, section chunking, metadata indexing |
| **Testing & Quality** | Vitest, Pytest, Playwright/Selenium, Mypy, Ruff, ESLint | Unit tests, end-to-end browser journeys, type validation, adversarial prompt injection checks |
| **DevOps & Windows** | PowerShell 7 launcher scripts, Git Worktrees | Process supervision, port health probing, collision-free background daemon management |

---

## 4. Curated Screenshot Assets & Showcase Guide

All high-resolution demonstration screenshots are stored in `portfolio-assets/hey-canvas/`:

### Primary Showcase Images (Recommended for Portfolio Headers & LinkedIn)

#### 1. Primary Full-Stack Showcase: `01-dashboard-desktop.png`
- **File:** `portfolio-assets/hey-canvas/01-dashboard-desktop.png` (1280x900)
- **Selection Rationale:** This image immediately demonstrates full-stack software engineering maturity. It showcases the comprehensive academic overview: enrolled active courses (CSE 4360, CSE 4310, CSE 3315), chronological upcoming deadlines with point values, quick-action study buttons, and real-time system readiness status.
- **Alt Text:** Desktop academic dashboard of Hey Canvas showing active courses, upcoming semester deadlines, and navigation panels.
- **Caption:** *"The Hey Canvas central academic dashboard: aggregates course enrollments, calculates upcoming deadlines deterministically from local SQLite, and displays local AI readiness."*

#### 2. Primary AI/ML Showcase: `02-ai-study-assistant.png`
- **File:** `portfolio-assets/hey-canvas/02-ai-study-assistant.png` (1280x950)
- **Selection Rationale:** Demonstrates applied AI engineering and RAG grounding. Shows a real student query (*"Help me prepare for Quiz 3 using the syllabus, announcements, and lecture materials"*) scoped to *CSE 4360: Autonomous Robot Design*. The response highlights the pedagogical breakdown, study roadmap, and citation cards pointing to specific professor documents and modules.
- **Alt Text:** Hey Canvas AI study assistant workspace showing course-scoped chat, grounded Quiz 3 preparation guidance, and source document citations.
- **Caption:** *"Course-scoped AI study assistant running Llama 3.2 locally. Grounded in actual course materials with transparent source citations and zero external API dependencies."*

---

### Supporting Feature Showcases

#### 3. Course Deep-Dive: `03-course-overview.png`
- **File:** `portfolio-assets/hey-canvas/03-course-overview.png` (1280x900)
- **Alt Text:** Course detail view for CSE 4360 showing syllabus overview, document preparation coverage badge, and module list.
- **Caption:** *"Deep course view detailing syllabus breakdowns, module structures, and on-demand document preparation coverage metrics."*

#### 4. Deadline Calendar: `04-deadline-calendar.png`
- **File:** `portfolio-assets/hey-canvas/04-deadline-calendar.png` (1280x900)
- **Alt Text:** Monthly calendar view displaying scheduled university coursework, exams, and project submission deadlines.
- **Caption:** *"Deterministic deadline calendar powered by local SQLite queries, providing exact date calculations without generative hallucinations."*

#### 5. Academic Knowledge & Source Evidence: `05-source-evidence.png`
- **File:** `portfolio-assets/hey-canvas/05-source-evidence.png` (1280x900)
- **Alt Text:** Document coverage and materials repository interface displaying indexed course files and extraction status.
- **Caption:** *"Managed materials repository showing parsed course documents, indexing status, and storage utilization."*

#### 6. Responsive Mobile View: `06-mobile-view.png`
- **File:** `portfolio-assets/hey-canvas/06-mobile-view.png` (390x844)
- **Alt Text:** Mobile responsive viewport of Hey Canvas on a smartphone screen showing clean navigation and dashboard cards.
- **Caption:** *"Responsive mobile layout (390px viewport) engineered with Tailwind CSS, ensuring accessibility on smartphones and tablets."*
