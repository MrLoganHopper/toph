# TOPH | Farm voice reporting

A React/Vite administration interface and mobile voice-reporting interface, backed by a separate FastAPI API, PostgreSQL/PostGIS, private versioned S3 storage, and OpenAI Realtime plus structured extraction.

**Read `docs/VERIFICATION.md` for the actual verification status.** This package contains the complete source, migrations, tests, provider adapters, and setup/deployment scripts. The delivery runtime could not install frontend dependencies or run a PostGIS server. A successful dependency-resolved build, real database tests, and live recording checks are required before using employee data. The included CI is a way to run those checks on a networked runner; its presence is not evidence that it has already passed.

**Security first:** rotate any database password previously pasted into a chat. Enter replacement secrets only in ignored `.env` files or the backend project's environment settings. No production secret or shared production password is included.

## 1. Fastest local start

Prerequisites: Python 3.12 or 3.13, Node.js 22.12+ with npm, and a running Docker installation. The default local database is PostgreSQL 16 with PostGIS 3.5. A managed development PostGIS database can replace Docker.

Extract the ZIP, open a terminal in its `toph` directory, then run:

```bash
python scripts/setup_local.py --seed
```

The script creates private local configuration with random secrets, creates `backend/.venv`, installs dependencies, starts the local PostGIS container, runs the migration, seeds fictional development data, and runs the frontend typecheck and production build. It asks you to choose a private development password. It stops on failures and preserves existing configuration on subsequent runs.

When setup succeeds:

```bash
python scripts/run_local.py
```

Open **http://localhost:5173**. Keep the terminal open. Ctrl+C stops the local servers.

Use username **`demo.admin`** for the admin interface or **`demo.worker1`** for the worker interface. Their password is the development password you entered during setup. `demo.admin2` and `demo.worker2` through `demo.worker8` are also provisioned. A second isolated farm uses the `cedar.` prefix.

The fictional seed has two farms, 20 users, ten fields, activity and fertilizer catalogs, 48 scheduled assignments, 48 reports, and tags. **Seed reports deliberately have no playable audio.** Audio playback must be tested with a new real worker recording after configuring S3 and OpenAI. The application gives a visible message for fixture audio instead of pretending playback succeeded.

Until `VITE_MAP_STYLE_URL` is configured, the map displays actual stored field boundaries on an explicitly labelled neutral background. It does not claim to display satellite imagery.

### Existing managed development database instead of Docker

```bash
python scripts/setup_local.py --managed --seed
```

This prompts for development runtime and migration connection URLs without displaying them. Use a separate development project. Runtime connections should use the transaction pooler; migrations use a direct connection or session pooler. Append `sslmode=require` at minimum for a remote database. Set the actual installed PostGIS schema when prompted. Database URL passwords must be URL-encoded.

Do not alternate Docker and managed setup against already-created `.env` files without explicitly editing/backing up those files. Existing configuration is preserved, not silently replaced. Do not run the development seed against your production project.

## 2. Manual setup and troubleshooting path

Use this section when a wrapper command fails and you need to rerun an individual step.

From the repository root:

```bash
python scripts/configure_local.py
python -m venv backend/.venv
```

On Windows PowerShell, use the virtual environment executable directly. Activation is optional:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
docker compose up -d --wait db
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.cli seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On macOS/Linux:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
docker compose up -d --wait db
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.cli seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open a second terminal at the repository root:

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server is at port 5173. `/api/*` is proxied to the backend on port 8000, preserving the browser origin. Open the frontend address, not the backend address, to log in. The backend liveness route is `http://127.0.0.1:8000/healthz`; a successful response establishes process liveness, not database or provider health.

Direct frontend dependencies and backend requirements are pinned. `package-lock.json` could not be generated without registry access in the delivery environment. The first successful `npm install` creates it. **Commit that lockfile** and use `npm ci` on subsequent clean installations. CI uses `npm ci` when a lockfile exists and saves a generated lockfile as an artifact otherwise. Review dependency audit results before a production release.

## 3. What is implemented

Admin routes include the welcome map reveal, dashboard, Activity Logs, map, Employees, Schedule, and Settings. Dashboard rows expand into the same report-detail component used by the activity grid, selected-field map results, and worker history. Reports include audio playback, waveform, transcript, field geometry, tags, planned times, activity, and fertilizer.

Filters live in the URL. Date, activity, fertilizer, field, employee, tag, and text conditions combine with AND, while text searches the permitted names, summaries, and tags. Sort direction, pagination, and selected-filter chips are functional. Rolling date presets mean last 24 hours, seven days, and 30 days; Today/This week/This month are separate farm-calendar presets. A week starts Monday in the farm timezone.

Settings has parallel activity and fertilizer catalogs with identical create/rename/delete permissions. Referenced catalog entries and fields are protected against deletion. Fields use validated GeoJSON Polygon/MultiPolygon input rather than a draw-on-map editor. Schedules are planned assignments, with explicit farm-timezone and daylight-saving handling.

The mobile worker flow has ready, connecting, listening/speaking, confirmation, review, saving, uploading, generating, completed, and retry states. The circle pulses before starting and responds to the mixed audio signal during a conversation. Five fixed questions cover activity, fertilizer, field, work details, and observations. Worker answers are confirmed before advancing by the voice instructions, with on-screen correction/confirmation controls.

Audio mixes the microphone and remote assistant stream. Final speaker-labelled transcript turns and waveform peaks are retained with a local IndexedDB draft. Incomplete transcription requires explicit review; a worker can add a clearly labelled manual correction. The app does not invent a transcript when transcription fails.

The upload pipeline saves metadata first, directly uploads the audio to S3, confirms size/type and a pinned version, then synchronously extracts and saves one structured report. Safe retries reuse the original client submission ID, recording, and explicit nullable shift. A completed draft is deleted locally only after the backend confirms a saved report.

Authentication uses Argon2id passwords, revocable opaque cookie sessions, server-checked memberships, CSRF and Origin checks, temporary-password changes, protected last-admin changes, and shared database rate counters. No Supabase Auth setup is required. The browser talks to FastAPI, not directly to PostgreSQL or the Supabase Data API.

## 4. Deliberate design decisions

Geist is imported through `@fontsource-variable/geist`; font binaries are not included in this repository. Dashboard layout proportions, whitespace, borders, row/detail structure, and controls follow the supplied references. Source screenshots are preserved under `docs/references/`.

The following specification semantics take priority over placeholder screenshot text:

- “Scheduled Now” is planned work, not attendance. “Extraction Confidence” is a model estimate, not measured response accuracy.
- “Recent Employee Logs” has no unread or “1 New” badge. Opening a report writes no view/read event.
- Activity and fertilizer are shown together. In the dashboard table they share a nearby column to preserve the reference proportions; each is independently represented and filtered.
- The worker counter is five questions, not the screenshot's repeated “1/3”.
- Audit Manager, Reports exports, Performance, Messages, and unsupported sidebar actions are hidden.
- The welcome screen opens after an admin signs in, as requested in the visual interaction notes. Its buttons lead to separate reusable routes.
- The field card grid appears below the map, matching the selected-field reference. Initial selection returns the latest ten reports; changing filters or sort changes that explicitly filtered selection.
- Farm initials replace a hardcoded profile photograph. This version has no avatar-upload feature.

A desktop image comparison, target-device voice session, and live imagery load have not been performed in the delivery runtime. Source-level styling is not a claim of pixel-perfect rendered verification.

## 5. Environment configuration

### Backend only: `backend/.env`, then Vercel backend environment

| Variable | Meaning |
|---|---|
| `APP_ENV` | `development`, `test`, `preview`, or `production`. |
| `DATABASE_URL` | Runtime PostgreSQL URL. Use the restricted role and transaction pooler in production. |
| `MIGRATION_DATABASE_URL` | Operator connection. Keep it local or in a restricted release environment, **not** the Vercel runtime project. |
| `POSTGIS_SCHEMA` | Actual extension schema, often `public` or `extensions`. |
| `APP_ORIGINS` | JSON array of exact frontend origins, with scheme and no trailing slash/path. |
| `COOKIE_SECURE` | `false` only for local HTTP; `true` for HTTPS deployments. |
| `CSRF_SECRET` | Independent random server secret, at least 32 characters. |
| `RATE_LIMIT_SECRET` | A different independent random server secret, at least 32 characters. |
| `AWS_REGION` | Region of the private general-purpose S3 bucket. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Restricted application IAM credentials. A configured SDK role can also be used where supported. |
| `S3_BUCKET` | Bucket name only, without an S3 URL. |
| `OPENAI_API_KEY` | Permanent project key, backend only. |
| `OPENAI_REALTIME_MODEL` | Enabled Realtime model ID from your project. |
| `OPENAI_TRANSCRIPTION_MODEL` | Enabled input-transcription model ID. |
| `OPENAI_EXTRACT_MODEL` | Enabled Responses API model supporting strict Structured Outputs. |
| `OPENAI_VOICE` | Compatible Realtime voice; initial setting is `marin`. |
| `AI_REQUEST_TIMEOUT_SECONDS` | Up to 45; 45 is the initial setting. |
| `DB_POOL_SIZE` | Starts at 1, with no overflow. Change only after concurrency testing. |
| `TRUST_VERCEL_PROXY` | Defaults to `false`. Enable only after verifying Vercel's trusted forwarding behavior for your deployment. Never trust arbitrary client forwarding headers. |

`MAX_RECORDING_BYTES` defaults to 26,214,400 and `MAX_RECORDING_DURATION_MS` to 600,000. These may be lowered, not raised beyond the database constraints. Metadata is limited to 256 KiB. Audio never traverses a Vercel function.

Generate each server secret independently:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Public frontend configuration

```dotenv
VITE_API_BASE_URL=/api/v1
VITE_MAP_STYLE_URL=<licensed MapLibre satellite style JSON URL>
```

`VITE_*` variables are bundled into the browser application. Put no database, AWS secret, permanent OpenAI key, or session secret there. The map URL may contain the map provider's restricted public browser token.

### Example production-only backend settings

```dotenv
APP_ENV=production
DATABASE_URL=<restricted transaction-pooler URL with sslmode=require or stronger verification>
POSTGIS_SCHEMA=<installed extension schema>
APP_ORIGINS=["https://YOUR-FRONTEND.vercel.app"]
COOKIE_SECURE=true
CSRF_SECRET=<one independent random secret>
RATE_LIMIT_SECRET=<a different independent random secret>
```

Add the AWS and OpenAI variables from the table. The app will not silently replace failed providers with test fixtures.

## 6. Supabase and PostGIS

Use a fresh development project for the first run and a separate project for production when possible. Supabase is the managed PostgreSQL host only. Do not enable `farm_app` in the Supabase Data API exposed-schema list, and do not grant it to anonymous/authenticated browser roles.

Copy connection details from your own project's Connect panel. The runtime uses the transaction pooler, generally port 6543. Migrations need the direct connection or a session-pooler connection, generally port 5432. Direct connectivity may depend on IPv6 availability; use the provider's session pooler when the local network cannot reach the direct endpoint. Do not substitute one connection type without checking the provider's actual host/user/port values.

Use URL-encoded passwords in connection strings. The runtime sets `prepare_threshold=None` for psycopg and starts with a one-connection SQLAlchemy pool.

To inspect the extension schema in Supabase's SQL editor:

```sql
SELECT n.nspname AS postgis_schema
FROM pg_extension e
JOIN pg_namespace n ON n.oid = e.extnamespace
WHERE e.extname = 'postgis';
```

Set `POSTGIS_SCHEMA` to that result. If PostGIS is absent, choose the intended schema and let the migration-capable connection enable it, or enable it using Supabase's extension controls. The migration explicitly refuses an extension-schema mismatch and leaves a useful error. Do not grant runtime DDL privileges to bypass a setup failure.

Run the initial migration with the virtual environment Python, from `backend/`:

```bash
python -m alembic upgrade head
```

After migration, create a restricted runtime database role from the repository root:

```bash
python scripts/create_runtime_role.py
```

Use the virtual environment Python for this command too. It prompts for a new `toph_runtime` password, grants application-table DML and schema usage, and keeps the Alembic version table inaccessible to that role. Construct a runtime URL for the dedicated role using the provider's supported connection syntax. Supabase pooler usernames include the role and project reference; use your project's actual pooler format. Store that restricted URL in `DATABASE_URL`. Keep the migration-capable URL separate.

For production, set `APP_ENV=production` in your private operator environment and run:

```bash
cd backend
python -m app.cli create-farm
```

The CLI prompts for the farm, timezone, first admin name, username, and password. It does not publish a default password. Do not seed production.

If the managed PostgreSQL major version differs from 16, select the corresponding PostGIS Docker image for local/integration parity before relying on migration tests for that deployment. Do not upgrade an existing Docker volume across major versions by merely changing the image tag; use a proper database upgrade/restore procedure.

## 7. AWS S3 setup

Create a **general-purpose private S3 bucket**, preferably near the API/database region. Keep Block Public Access enabled, use Bucket owner enforced object ownership, enable versioning, and use server-side encryption. The supplied application permissions assume ordinary S3-managed encryption; a customer-managed KMS key requires its additional appropriately restricted permissions.

Copy `docs/aws-iam-policy.json`, replace `YOUR-BUCKET`, and attach the policy to the dedicated application IAM identity. It grants only `s3:PutObject`, `s3:GetObject`, and `s3:GetObjectVersion` for `farms/*`. Do not grant `s3:*`. **`s3:HeadObject` is not an IAM action**; AWS documents `s3:GetObject` as the relevant HEAD permission. This corrects a literal action name in the original supplied setup notes.

Copy `docs/s3-cors.json` into the bucket CORS configuration. Replace the frontend placeholder with the exact HTTPS origin. Keep the localhost origin only on a development bucket/configuration. If you use `http://127.0.0.1:5173`, add that exact development origin as well. Upload and playback need POST/GET/HEAD; the app session cookie is omitted from S3 requests.

Set the backend's region, bucket name, application access key ID, and secret access key. Confirmed audio versions are intentionally retained. **Do not add lifecycle expiration for noncurrent versions that might still be referenced by a recording.** A subsequent upload can make the pinned version noncurrent while it remains the authoritative playback target. Use an explicit retention and backup policy, not a short blanket expiration.

The app signs a restricted form for the exact generated key, content type, and expected size. It verifies a HEAD response and saves the version ID before extraction. Its playback URLs address that pinned version. An expired playback link can be renewed without changing the stored recording.

## 8. OpenAI setup

Create or use an OpenAI project with appropriate billing, budgets, and model access. Put the permanent project key and enabled model IDs in the backend environment. Model IDs are intentionally configurable and blank in `.env.example`; this repository does not invent model availability for your account.

Realtime credentials are minted server-side at `/v1/realtime/client_secrets`. The browser receives a short-lived credential and connects directly to `/v1/realtime/calls` over WebRTC. Input transcription must be enabled. The code receives both audio streams and final transcript events, then records the mixed signal.

Extraction uses `/v1/responses` with `store:false`, a strict JSON-schema output format, all required keys, explicit nullable unknowns, and `additionalProperties:false`. Catalog IDs are validated against the farm after the model responds. Worker statements supply facts; prompts, schedules, and assistant suggestions are not proof of completed work.

Provider failures remain visible. A timeout preserves the confirmed recording and permits a same-recording retry. Credentials or model access failures cannot be validated by merely inspecting this source; run the live voice checklist below.

## 9. Satellite map setup

Provide a licensed MapLibre-compatible satellite **style JSON URL** in `frontend/.env` and the frontend Vercel environment. A static image, a Google Maps page URL, and a secret backend API key are not interchangeable with that style URL.

Retain the required attribution, and configure the provider's browser-token origin restrictions for localhost and the actual deployed frontend as appropriate. Restart Vite after a local environment change and rebuild/redeploy after a Vercel frontend environment change.

The seed geometry is fictional and will not necessarily match a farm shown in the Figma image. Add the real farm's field boundaries in Settings for production. Map selection represents field geometry, never a live employee GPS dot.

## 10. GitHub and two-project Vercel deployment

First run the local build/test gates. The workflow in `.github/workflows/ci.yml` runs the backend suite against real PostGIS, frontend checks/build, and Chromium browser tests with isolated fixture data. It uses no production provider keys. Review its result before approving a production release.

From the repository root:

```bash
git init
git add .
git status
```

Verify that no real `.env` or credential file is staged. Add the generated `frontend/package-lock.json` after the first successful install. Then:

```bash
git commit -m "Implement TOPH farm reporting app"
git branch -M main
git remote add origin <YOUR-EMPTY-GITHUB-REPOSITORY-URL>
git push -u origin main
```

Create **two Vercel projects** connected to that repository:

| Project | Root | Framework/build |
|---|---|---|
| API | `backend` | FastAPI; entry point `app/main.py`, `app.main:app` declared in `pyproject.toml`; function duration 60 seconds. |
| Web | `frontend` | Vite; Node 22; build `npm run build`; output `dist`. |

Use stable project production origins, not a per-commit preview URL. Put runtime database, AWS, OpenAI, Origin, cookie, and server-secret variables in the **backend** project's production environment. Put only the two `VITE_*` variables in the **frontend** project. Do not put `MIGRATION_DATABASE_URL` in the Vercel runtime project.

Deploy the backend. Run migrations and bootstrap the production admin once using the separate operator connection; these are explicit release actions, never request-time startup hooks.

Set the frontend rewrite to the stable backend origin:

```bash
python scripts/set_backend_origin.py https://YOUR-FASTAPI-PROJECT.vercel.app
git add frontend/vercel.json
git commit -m "Configure production API origin"
git push
```

The `/api/:path*` rule must remain **before** the SPA fallback. Use the actual frontend's exact stable origin in backend `APP_ORIGINS`, and the same frontend origin in S3 CORS and the map provider's restrictions. Environment updates require redeployment of the affected project.

A project's deployment protection can block proxied API requests before FastAPI sees them. Verify the production backend is reachable by the intended frontend rewrite under your selected Vercel protection configuration. Preserve application session authentication and CSRF checks. Do not solve a routing/protection issue by removing them.

Preview environments need separate database/storage data and explicit origins. Do not allow every `*.vercel.app` origin or send arbitrary preview builds to production records.

## 11. Verification commands

Use the backend virtual environment Python from the repository root:

```bash
python scripts/verify.py
```

This runs backend tests, actual OpenAPI generation/route coverage, frontend typecheck, lint, frontend unit tests, and production build. Missing PostGIS configuration is reported as a skip, never a pass.

For real database tests, create a **disposable database whose name ends in `_test`** and enable PostGIS. Set these only for that test run:

```dotenv
TEST_DATABASE_URL=<disposable PostgreSQL/PostGIS connection URL>
TOPH_TEST_RESET=YES
```

Then run:

```bash
python scripts/verify.py --require-db
```

The integration fixture resets `farm_app` in that test database. It refuses to run with an ordinary production database name or without the explicit reset authorization. Never point `TEST_DATABASE_URL` at employee data. CI creates its own disposable database automatically.

To run browser tests after starting the backend and seeding development data, set `E2E_PASSWORD` to your private development seed password in that terminal, then:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

Playwright starts the local Vite server if necessary. `E2E_BASE_URL` can target an already running **development** frontend instead. These tests exercise Chromium and a mobile-sized viewport, not physical iPhone Safari or Android media behavior.

After deployment, run the read-only application smoke script through the **frontend** origin:

```bash
python scripts/smoke.py https://YOUR-FRONTEND.vercel.app
```

It prompts for an admin username/password, checks API JSON errors, login cookies, private cache headers, the core reads, nested frontend refresh, and logout revocation. It does not create a paid voice session or upload audio.

### Required live browser checks

Use a dedicated test farm and worker, then verify:

1. Log in as an admin, add/edit an activity and fertilizer, and confirm a referenced entry cannot be deleted. Create a worker and complete the temporary-password change.
2. Confirm dashboard expansion, all date/activity/fertilizer/field filters, removable chips, pagination, and selected-field reports. Reload a nested route.
3. On actual iPhone Safari and Android Chrome, grant the microphone after pressing the circle. Complete the five questions and confirmations. Listen to the local review recording and verify both voices are audible.
4. Submit the recording. Verify it appears in worker history and the admin dashboard with the correct activity, fertilizer, field, worker, and planned-shift context.
5. Play and seek the saved audio. Renew an expired playback link. Verify the bucket object remains private and the confirmed version is used.
6. Interrupt upload or simulate an extraction failure in a development environment. Retry without rerecording; verify only one report is saved. Do not deliberately break production configuration to run this test.
7. Test a worker trying another worker's log and an admin trying another farm's resource. Verify requests are denied by the API, regardless of frontend controls.

Keep the recording page open during capture and upload. Browsers can suspend tabs or lose active recordings during navigation/crashes. Completed IndexedDB drafts have a retry path; native/background/offline voice recording is outside this version's promises.

## 12. Operational commands and release safety

From `backend/`, with the operator environment and virtual environment Python:

```bash
python -m app.cli create-farm
python -m app.cli attach-user
python -m app.cli reset-password
python -m app.cli maintenance --dry-run
```

`maintenance --apply` removes expired authentication/rate records and sufficiently old unconfirmed metadata. It does not remove confirmed audio or silently clean S3 objects. Global admin/shared-account password recovery uses the operator CLI, not an ordinary farm admin's reset action.

Configure database backups and audio retention, and test restoration before retaining important employee records. Review deployment access, dependency audits, model budgets, and log redaction. Do not record highly sensitive information as part of a farm-work interview without an appropriate organizational policy.

## 13. Troubleshooting

| Symptom | Check |
|---|---|
| Setup refuses to overwrite an environment file | Existing files are retained intentionally. The setup wrapper reuses complete files; edit or back up an incomplete pair. |
| `npm` is missing or install cannot reach the registry | Install Node 22.12+, reopen the terminal, and verify network/proxy access. Do not treat an install failure as a successful build. |
| Python cannot import `psycopg` or `geoalchemy2` | Use `backend/.venv` and rerun its requirements installation. Integration tests require real PostGIS, not SQLite. |
| Database unavailable/timeout | Check runtime versus migration URL, password encoding, SSL settings, provider host/port, network reachability, and app schema grants. |
| PostGIS schema mismatch | Set `POSTGIS_SCHEMA` to the extension's actual schema and rerun the migration with operator credentials. |
| Login fails with Origin error | Exact frontend origin must be in backend `APP_ORIGINS`; do not include a path or trailing slash. Redeploy after changing it. |
| API returned HTML | Fix rewrite precedence/destination and deployment protection. `/api/v1/not-a-route` must return JSON 404. |
| Cookie missing after deployment | Check HTTPS, `COOKIE_SECURE=true`, same-origin frontend `/api` access, and the real rewrite's Set-Cookie forwarding. |
| Voice provider unavailable | Verify project billing, key, all model IDs and their access, microphone permission, and network restrictions. |
| Upload fails or bucket versioning required | Verify bucket region, private IAM permissions, exact CORS origin, versioning, and expected content type. Retain the local draft and retry. |
| Seed audio unavailable | Expected. Make a real worker recording to test actual upload/playback. |
| Imagery missing | Configure a valid licensed MapLibre style URL/public token, provider origin restrictions, attribution, and WebGL support. |
| Unknown catalog values in a report | Unknowns are nullable. Clarify the spoken activity/fertilizer/field and ensure the correct farm vocabulary exists. The model cannot create a catalog entry. |

## 14. Repository map and sources

`frontend/src/features/` contains the replaceable route components. `backend/app/api/` handles HTTP, `services/` business behavior, `models/` persistence, `schemas/` safe DTOs, and `providers/` the live S3/OpenAI boundaries. `backend/alembic/` holds the frozen initial migration. Original specifications and screenshots are under `docs/`.

Implementation-specific differences and visual defaults are in `docs/IMPLEMENTATION_NOTES.md`. Actual completed and blocked checks are in `docs/VERIFICATION.md`. The compact deployment sequence is in `DEPLOYMENT_CHECKLIST.md`.

Official provider references checked during this implementation:

- Vercel FastAPI and entry-point configuration: https://vercel.com/docs/frameworks/backend/fastapi
- Vercel external rewrites: https://vercel.com/docs/routing/rewrites
- Supabase connection modes: https://supabase.com/docs/guides/database/connecting-to-postgres
- PostGIS Docker images: https://github.com/postgis/docker-postgis
- S3 HEAD permissions: https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
- OpenAI browser WebRTC: https://developers.openai.com/api/docs/guides/voice-webrtc
- OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- MapLibre satellite rendering: https://maplibre.org/maplibre-gl-js/docs/examples/display-a-satellite-map/

Provider accounts, billing, region selections, and live model/tile access are external setup requirements. They have not been provisioned or changed by this source package.
