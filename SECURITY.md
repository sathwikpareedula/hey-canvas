# Security and privacy

Hey Canvas is an independent, local-first student project and **not a hosted production service or security-certified product**.

## Intended boundaries

- Canvas integration is designed for **read-only access**. Do not use this project to submit, modify, or delete Canvas records.
- Keep `.env`, tokens, personal SQLite databases, logs, downloaded course files, and private student records out of Git and public screenshots.
- The backend is intended for local loopback access by default. Do not expose it directly to the public internet without an independent security review.
- Local Ollama inference can run on-device; **Canvas synchronization still contacts Canvas**. Optional external AI providers and browser speech functionality may have separate data-handling implications.
- Academic retrieval treats course materials as untrusted evidence, not executable instructions. Verify generated academic guidance against primary sources.

## Local runtime security updates (October 2026)

Hey Canvas does not bundle Node.js or Ollama; each user must update those programs on their own computer.

- **Node.js:** The October 21, 2026 security releases patched vulnerabilities in supported Node 22, 24, and 26 lines. Use Node 22.23.4+ on the 22.x line or Node 24.22.1+ on the 24.x line (or another currently patched supported line). See the [official Node.js security release](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases).
- **Ollama:** Local inference is optional. Versions older than 0.35.0 may lack the fix for [CVE-2026-103663](https://nvd.nist.gov/vuln/detail/CVE-2026-103663), a path-traversal issue in the model-pull endpoint that can lead to code execution in some deployments. Ollama 0.34.2 also fixed [CVE-2026-108836](https://nvd.nist.gov/vuln/detail/CVE-2026-108836), a pull-API SSRF issue. Use Ollama 0.35.0+ and keep its HTTP API bound to loopback rather than exposed to other devices or the internet.
- Upgrading this repository does **not** automatically upgrade an existing user's Node.js or Ollama installation. Check installed versions before using real Canvas credentials.

## Responsible reporting

If you find a vulnerability or suspected credential exposure, do **not** open a public issue containing secrets, personal data, or exploit details. Contact the repository maintainer privately through an appropriate GitHub private reporting channel if one is enabled. If no private reporting channel is available, request a secure contact method without disclosing the issue publicly.

## Public source release and verification

This source repository is public. The original development repository remains private. The release's source-history and tracked-file secret scans were reported clean in [GitHub Actions run #39676551978](https://github.com/sathwikpareedula/hey-canvas/actions/runs/39676551978), which also passed backend, frontend, synthetic browser, and Windows synthetic acceptance checks.

These scans do not guarantee that all future changes, third-party components, or runtime configurations are free of vulnerabilities. The current public repository's history and contents are the relevant publication scope; historical audit findings from the separate private development repository do not describe findings in this clean public history.

For limitations and historical testing context, see [VERIFICATION.md](VERIFICATION.md). The optional local Ollama mode has different behavior from the deterministic synthetic demonstration. Never treat a scripted demo response as proof of generated-model accuracy.
