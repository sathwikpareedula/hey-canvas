# Security and privacy

Hey Canvas is an independent, local-first student project and **not a hosted production service or security-certified product**.

## Intended boundaries

- Canvas integration is designed for **read-only access**. Do not use this project to submit, modify, or delete Canvas records.
- Keep `.env`, tokens, personal SQLite databases, logs, downloaded course files, and private student records out of Git and public screenshots.
- The backend is intended for local loopback access by default. Do not expose it directly to the public internet without an independent security review.
- Local Ollama inference can run on-device; **Canvas synchronization still contacts Canvas**. Optional external AI providers and browser speech functionality may have separate data-handling implications.
- Academic retrieval treats course materials as untrusted evidence, not executable instructions. Verify generated academic guidance against primary sources.

## Responsible reporting

If you find a vulnerability or suspected credential exposure, do **not** open a public issue containing secrets, personal data, or exploit details. Contact the repository maintainer privately through an appropriate GitHub private reporting channel if one is enabled. If no private reporting channel is available, request a secure contact method without disclosing the issue publicly.

## Public source release and verification

This source repository is public. The original development repository remains private. The release's source-history and tracked-file secret scans were reported clean in [GitHub Actions run #39676551978](https://github.com/sathwikpareedula/hey-canvas/actions/runs/39676551978), which also passed backend, frontend, synthetic browser, and Windows synthetic acceptance checks.

These scans do not guarantee that all future changes, third-party components, or runtime configurations are free of vulnerabilities. The current public repository's history and contents are the relevant publication scope; historical audit findings from the separate private development repository do not describe findings in this clean public history.

For limitations and historical testing context, see [VERIFICATION.md](VERIFICATION.md). The optional local Ollama mode has different behavior from the deterministic synthetic demonstration. Never treat a scripted demo response as proof of generated-model accuracy.
