# Engineering Hey Canvas

**Full-stack development, academic data engineering, and reliability-focused AI integration.**

## The problem

As a computer science student, I found that information needed for a single study session could be scattered across Canvas courses, assignments, announcements, syllabi, and lecture materials. Generic chatbots can explain concepts, but they often have no reliable way to identify the correct course, confirm an actual deadline, or distinguish a professor's instructions from an invented answer.

I built Hey Canvas to connect those two workflows: trustworthy academic records and context-aware study assistance.

## The solution

Hey Canvas is a Windows-oriented, local-first academic workspace. A Next.js/React interface brings courses, upcoming work, materials, and conversations together. A Python/FastAPI backend synchronizes authorized Canvas records through read-only APIs, normalizes them into SQLite, and prepares supported document content for course-scoped retrieval.

The assistant separates structured facts from generated explanations. Known deadline and assignment questions can use deterministic data paths rather than asking a language model to manufacture an answer. For explanations and study guidance, the orchestration layer can use course evidence with a locally hosted Ollama model.

## Architecture and implementation

```text
Read-only Canvas API
        |
Secure incremental synchronization
        |
FastAPI + SQLAlchemy + SQLite
        |                         \
Structured academic records     Managed document cache
        |                         |
Deterministic academic queries   Text preparation, provenance, indexing
        \                         /
          Course-scoped evidence and routing
                         |
              Assistant orchestration
               /                 \
      Deterministic answers    Ollama inference
               \                 /
           Streaming student interface
                Next.js / React
```

The implementation spans **Python, FastAPI, Pydantic, SQLAlchemy, SQLite, HTTPX, Next.js, React, TypeScript, Ollama, pytest, mypy, Ruff, Vitest, and Windows PowerShell**.

## Hard engineering problems

### Building a knowledge system, not just a file list

Canvas exposes structured assignment data as well as files that require separate discovery, download, parsing, and indexing. I designed the document workflow so that **file metadata is not confused with searchable content**. Managed storage tracks preparation and source state; incremental, bounded processing avoids indiscriminate downloads. The assistant must recognize missing or stale evidence instead of presenting it as verified.

### Protecting course context

Academic help is only useful if the answer belongs to the correct course and assessment. The application keeps retrieval course-scoped, uses structured academic data where possible, and treats announcements and document text as **untrusted evidence rather than instructions**. Regression cases cover misleading authority claims, quoted prompt injections, course changes, and assessment exclusions.

### Getting streaming and cancellation right

A streaming AI response involves asynchronous request setup, database access, model generation, network delivery, and cleanup. Hard cancellation uncovered a SQLAlchemy session-lifecycle race. I added explicit coordination around setup and teardown and used targeted lifecycle tests to verify cancellation behavior without disrupting the database session.

### Distinguishing model behavior from application correctness

A slow or incorrect answer may come from the model, incomplete course evidence, or routing logic. I tested deterministic academic paths independently from real Ollama inference and added narrowly scoped deterministic explanations for stable graph-search concepts, such as BFS versus DFS and A* heuristic behavior. This improved targeted cases without claiming that a local 3B model is universally fast or accurate.

## Verification

At the recorded V1.2 local integration checkpoint `e109d2c`:

- **1,076 backend pytest tests passed**; Ruff and strict mypy passed across **206 Python files**.
- **311 frontend tests passed** with **12 skipped**; TypeScript, ESLint, and the Webpack production build passed.
- **7 Windows launcher tests passed**.
- A full 22-scenario CPU-hosted Ollama rerun passed **16/22**. Five scenarios exceeded the 120-second bound; one comparison case returned a fallback outside its acceptance rule. All four originally failing safety/correctness cases passed in that rerun.
- Three additional targeted real-provider scenarios passed after deterministic routing improvements; those tests are **not** a replacement for a full 22-case evaluation.

These results describe a **local development candidate**, not production use or accuracy with every course. Document coverage is incomplete, conversations currently persist in the browser rather than in a durable backend message store, and full final physical-device and security acceptance remain open.

## The result

Hey Canvas demonstrates how I approach a full-stack AI product: establish dependable data access, separate verified facts from inference, preserve source provenance, make asynchronous operations safe to interrupt, and test actual model behavior rather than relying on a polished demo.

The goal was never simply to add a chatbot to Canvas. It was to build the engineering around a course-aware assistant so it can be useful, inspectable, and honest about what it knows.

---

**Project status:** V1.2 local acceptance candidate; release hold active. Independent project, not affiliated with or endorsed by Instructure. Synthetic fixtures are used for public screenshots. The application does not submit assignments or modify Canvas course data.
