# Verification and project scope

Hey Canvas V1.2 is a **local-first acceptance candidate**, not a publicly deployed production service.

## Latest verified review-branch acceptance (October 20, 2026)

At functional checkpoint `d84f842100937abd8623d095c294e9269a9b5d34`, [GitHub Actions run 39543019631](https://github.com/sathwikpareedula/UTA-Academic-Copilot/actions/runs/39543019631) completed:

| CI job | Result |
|---|---|
| Backend checks | **PASS** |
| Windows backend and fresh-checkout synthetic startup/stop/restart | **PASS** |
| Synthetic browser journeys | **PASS** (22/22 reported) |
| Complete Git-history and working-tree Gitleaks scans | **PASS** with 13 individually reviewed exact-fingerprint classifications |
| Frontend lint, typecheck, tests, production build and production-only audit | **PASS** |
| Development-inclusive dependency audit | **FAIL**: upstream `braces` advisory `GHSA-vfj7-8cjw-p6xm` in the ESLint toolchain |

The **overall workflow is red**; do not present it as all checks passing. The production-only npm audit reports zero vulnerabilities. The five development audit findings share a transitive chain through `eslint-config-next`, `@next/eslint-plugin-next`, `fast-glob`, `micromatch`, and `braces`. At this checkpoint, no compatible patched upstream version was verified, and the incompatible forced downgrade was not used.

The 13 reviewed history findings remain in reachable commits but are narrowly classified in `.gitleaksignore` by immutable fingerprint; this is **not** a history rewrite or a claim that all history is secret-free independent of the review.

A fresh GitHub-hosted Windows checkout successfully installed dependencies, initialized a disposable SQLite database, started the backend/frontend without Canvas credentials or Ollama, served health/startup/dashboard endpoints, handled repeated launch, and stopped/restarted its owned processes. It also launched the explicit isolated demo, verified the synthetic provider, and confirmed that the populated course catalog contained only synthetic course identifiers. This **does not verify** real institutional Canvas authorization/sync, real local-model inference, physical microphone permission behavior, or installation on every user's machine.

**Decision:** suitable for a controlled private release-candidate evaluation with documented limitations. Public release and merge remain on hold pending explicit authorization and remaining acceptance/risk decisions.

## Earlier recorded verification

These results were reported for the local application checkpoint `e109d2cf305a3f44e4580683f22c0be9fd44b654`:

| Check | Result |
|---|---|
| Backend pytest | 1,076 passed |
| Python Ruff and strict mypy | Passed; 206 files checked by mypy |
| Frontend Vitest | 311 passed, 12 skipped |
| TypeScript, ESLint | Passed |
| Next.js production build | Passed with Webpack; 20 routes |
| Windows launcher automated tests | 7 passed |
| Full real Ollama evaluation (`llama3.2:3b`) | 16 of 22 passed |
| Later targeted real-provider routing checks | 3 of 3 passed; **not** a complete 22-case rerun |

In the full real-model run, average first-text latency was 32.809 seconds and average total response time was 53.032 seconds. Five cases exceeded 120 seconds and one comparison case returned a fallback that did not meet its evaluation rule. These measurements describe the tested CPU environment, not general performance.

## GitHub Actions validation of the cleaned snapshot

The automated workflow [V1.2 Academic Evidence Checks](https://github.com/sathwikpareedula/UTA-Academic-Copilot/actions/runs/39239867977) ran against the cleaned review branch on October 19, 2026:

- **Backend checks:** passed.
- **Windows backend and launcher checks:** passed.
- **Synthetic browser journeys:** passed.
- **Frontend lint, typecheck, tests, production build, and production-only dependency audit:** passed.
- **Full frontend job:** failed solely at the development-inclusive npm dependency audit. That audit reported five high-severity advisories in the transitive ESLint glob tooling chain (`eslint-config-next` → `@next/eslint-plugin-next` → `fast-glob` → `micromatch` → `braces`). The production-only audit reported **zero vulnerabilities**. The suggested forced fix would introduce a breaking ESLint configuration downgrade and was not applied.

These checks do not test real Canvas credentials or replace the complete real-Ollama acceptance suite.

## Additional local Windows acceptance observation (October 19, 2026)

A separate, fresh checkout of the V1.2 application candidate was installed on Windows with Python 3.13.1, Node.js 22.11.0, npm 10.9.0, and Ollama 0.20.0. The Python dependency check and frontend TypeScript typecheck completed without errors. The application launched with its newer dashboard and assistant interface.

During manual testing, the application displayed a successful Canvas synchronization and populated academic deadlines. This is **a user-observed local test**, not a repeatable public demonstration or a credential-free CI validation. No private course database or Canvas token is included in this repository.

The manual test also exposed limitations: local-model explanations could be slow, one question timed out and fell back to indexed evidence, and responses were not consistently useful when assignment descriptions were missing. A successful sync indicator does not by itself validate every synchronized record or every AI answer. These issues remain open; no performance or accuracy guarantee is claimed.

## Latest review-branch CI observation (October 20, 2026)

GitHub Actions run [39369667628](https://github.com/sathwikpareedula/UTA-Academic-Copilot/actions/runs/39369667628), associated with documentation commit `d48aab91`, completed with:

| Job | Result |
|---|---|
| Backend | Passed |
| Synthetic browser | Passed |
| Windows backend synthetic | Passed |
| Frontend | Failed at **full development-inclusive dependency audit** |

The frontend job's failing step was the full dependency audit. **Do not infer that all other frontend steps passed without examining their individual results.** This is not a clean green workflow. It does not replace physical Windows acceptance, real Canvas sync testing, or a complete secret/history audit.

A source-only checkout of this private repository could not be cloned into the separate execution container because external GitHub DNS/network access was unavailable. Accordingly, **fresh-install and full local test execution were NOT RUN in that container**. GitHub-hosted synthetic CI is the only newly retrieved automated evidence described here.

The four supplied *real* screenshots were visually reviewed. They show actual course names, assignment details, and sync information; the Learn-mode response also includes an oversimplified robotics explanation. They were **not committed**. Existing synthetic README screenshots remain the safer publication option pending a new verified capture set.

## Limitations

- Academic file metadata is not equivalent to downloaded, parsed, and indexed material. Coverage depends on successful preparation.
- Completed chat messages persist in browser localStorage, not in a durable backend message history.
- Twelve frontend integration-marked tests were skipped in the recorded ordinary test run.
- The complete real-model suite has not been rerun after the final targeted deterministic-routing changes.
- Physical Windows and microphone acceptance, development dependency advisories, and further security review remain open.
- The Canvas client is read-only by design, but synchronization still communicates with Canvas; this project makes no blanket zero-egress or regulatory certification claim.

## Reproducing the project

The source includes backend and frontend tests, synthetic academic fixtures, local startup scripts, and configuration examples. Run tests with a disposable SQLite database and synthetic demo data. Never commit Canvas credentials, downloaded real course material, or private student records.

The repository is an independent student project and is not affiliated with or endorsed by Instructure.
