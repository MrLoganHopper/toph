# TOPH verification report

Recorded: 2026-09-18 02:11 UTC. Code and test source are included in this handoff. No production service was created, changed, or deployed. The previously shared database credential was not used.

## Release status

**Implementation and repository handoff are complete for the scoped source. Production verification is incomplete.** A full installed-dependency frontend build, migrations/seed against real PostGIS, authenticated database-backed flows, live providers, and the deployed rewrite must pass before real employee use. This document reports checks that actually ran and distinguishes them from tests that were only written.

## Checks that passed here

| Check | Actual result and scope |
|---|---|
| Backend pytest | **78 passed, 15 skipped.** Passed checks cover validation, timezone/DST helpers, safe DTO/contract shape, HTTP rejection/error/cache behavior, and provider request/response boundaries. |
| Backend process startup | **Passed.** Started real Uvicorn against `app.main:app`, checked HTTP, and shut down cleanly. |
| Public HTTP checks | `/healthz` returned 200 JSON, unknown API path returned 404 JSON, anonymous `/me` returned 401, and invalid-Origin login returned 403. API errors had no-store headers. |
| Actual OpenAPI generation | **Passed.** Generated `docs/openapi.json` from FastAPI. All **44** endpoint-inventory method/path combinations are present. This is route coverage, not proof that each database query executed. |
| Python syntax | **Passed.** Application, migrations, tests, and operator/setup scripts compile. |
| TypeScript source parsing | **Passed for 27 application TS/TSX files**, with relative-import resolution. This is parsing/transpilation, not a complete dependency-resolved typecheck. |
| Frontend source-logic audit | **32 checks passed** by transpiling the actual helper/submission modules and exercising them in Node with explicitly mocked API, device-storage, and media boundaries. This is not Vitest, React rendering, or a Vite production build. |
| Repository configuration | JSON, TOML, and YAML parsed; project/requirements dependencies match; referenced local documentation files exist. |
| Handoff hygiene | The archive excludes actual `.env` files, private keys, dependency directories, local audio, font binaries, and caches. A pattern-based credential scan found no real access keys or private key blocks. A scan is not a complete security audit. |

Raw evidence is in `docs/verification/`. The frontend logic audit checks date/filter normalization, independent activity/fertilizer filters, waveform bounds, format feature detection, direct-upload ordering, retry reuse, transcription rejection, failed-upload/extraction retention, and successful-server-save handling when local cleanup fails.

## Explicit test boundaries

AWS unit tests use **botocore Stubber**, and OpenAI unit tests use **httpx MockTransport**. They test the real adapter code and request/response behavior without performing a live external operation. They do not establish AWS IAM/CORS correctness or model access in an owner's account. These substitutions exist only in tests. Production adapters make real requests and show errors when unavailable.

An additional internal-interface TypeScript audit used external-library boundary declarations to look for local interface mismatches. It found none, but those declarations are not a substitute for installed library types. They are not shipped or enabled in the application, and the audit is not counted as a passed production typecheck.

The delivery runtime used Python 3.13.5 and Node 22.16.0. CI is configured for Python 3.12 and Node 22 with the pinned application dependencies. The CI workflow has not run here.

## Checks blocked or not run

| Check | What happened / what is still required |
|---|---|
| Frontend dependency installation | Registry access was unavailable; the offline cache was insufficient. React, Vite, and the project's other required packages could not be installed. |
| `npm run typecheck` | **Attempted and failed because required modules/type declarations were absent**, with cascading diagnostics. No claim of a passing complete TypeScript check. Rerun after installation and resolve any remaining diagnostics. |
| `npm run lint` | **Attempted and blocked by missing project ESLint dependencies.** |
| `npm test` | **Attempted and blocked because Vitest was not installed.** Four frontend unit-test files are included. |
| `npm run build` | **Attempted and failed at TypeScript's missing-dependency stage.** No production bundle was produced. |
| Frontend lockfile | No invented lockfile is included. Direct versions are pinned. A successful first `npm install` generates `package-lock.json`; commit it and use `npm ci` afterward. |
| PostGIS migration and seed | **Not executed here.** No PostgreSQL/PostGIS server or Docker was available, and the missing psycopg/GeoAlchemy2 packages could not be fetched. |
| Real database integration suite | **15 tests skipped** because `TEST_DATABASE_URL` was not configured. They cover real migration/seed, authentication, authorization, foreign-key isolation, concurrency, queries, spatial data, and recording/report persistence. |
| Browser rendering and visual comparison | Playwright tests are included but were not executed. Dashboard visual fidelity and animation behavior have not been screenshot-verified. |
| AWS S3 | No live bucket upload, version verification, signed playback, or range seeking performed. |
| OpenAI | No live Realtime session, input transcription, or structured extraction performed. |
| Actual mobile devices | iPhone Safari and Android Chrome microphone, mixed audio, interruption/retry, playback, and seeking remain manual smoke tests. |
| Vercel | No project deployment, real reverse-proxy cookie/Origin check, or deployed route-refresh smoke test performed. |

## Run the remaining checks

On a networked machine, start with `python scripts/setup_local.py --seed` from the root, or use `--managed --seed` for a dedicated managed development PostGIS database. The script installs dependencies, migrates/seeds development data, and requires a frontend typecheck/build to succeed. It stops on errors and does not relabel a failed step as passed.

Run `scripts/verify.py` with the backend virtual-environment Python. To require database coverage, supply an explicitly disposable database whose name ends in `_test`, set `TOPH_TEST_RESET=YES`, and run `scripts/verify.py --require-db`. The database tests destructively reset the application schema in that test database. Never point them at production.

The included GitHub Actions workflow provisions its own disposable PostGIS service, runs backend and frontend tests/build, and runs Chromium smoke tests. A successful workflow result is additional evidence only after it actually executes. It uses no real provider credentials, so real voice and storage still require live tests.

Complete the deployed `scripts/smoke.py` check and the live worker-recording checklist in the README before release. Passing liveness, syntax, or route coverage alone is insufficient to establish an end-to-end working deployment.
