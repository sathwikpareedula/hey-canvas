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

## Release status

V1.2 remains under release hold. A full pre-publication secret/history audit and physical Windows acceptance are required before changing repository visibility. A clean `.gitignore` alone does not prove Git history is free of secrets. See [VERIFICATION.md](VERIFICATION.md) for current test scope and limitations.

### Historical secret-scan classifications

The repository uses `.gitleaksignore` only for 13 reviewed, immutable finding fingerprints:

- Twelve findings belong to a transient `.next-verify-18411` development build committed in `908c76c`. They are framework-generated preview/build secrets, not Canvas credentials, provider keys, private student data, or deployed application secrets. The generated tree is no longer present at `HEAD`.
- One finding belongs to `backend/tests/services/test_sync_orchestrator.py` in `9ef3616`. It is a deliberately synthetic credential-redaction test value, not a usable credential. The current fixture constructs the marker without embedding a scanner-shaped token.

No rule, path, directory, or commit is broadly excluded. Any finding with a different fingerprint continues to fail the complete-history and checked-out-file scans. This classification does not authorize reuse or deployment of the generated preview secrets.
