# TOPH deployment checklist

The project code is packaged. A full frontend build and the real database/provider tests still need to pass on a networked machine. Start with the setup command so dependency or build errors are discovered before spending time on provider configuration. Full details and troubleshooting are in `README.md`.

## 1. Extract and verify the application

Extract `TOPH_FINAL.zip` and open a terminal in `toph`.

With Python 3.12/3.13, Node 22.12+, and Docker running:

```bash
python scripts/setup_local.py --seed
python scripts/run_local.py
```

Choose your own development seed password when asked. Open `http://localhost:5173`, log in as `demo.admin`, and check the dashboard and logs. Use `demo.worker1` for the mobile worker flow.

A managed development PostGIS database can replace Docker:

```bash
python scripts/setup_local.py --managed --seed
```

This asks for the connection URLs privately. Do not use the previously shared database password. Rotate it first. Do not seed production.

Run the tests with the virtual environment Python, using a second terminal:

```powershell
# Windows, from the repository root
.\backend\.venv\Scripts\python.exe scripts/verify.py
```

```bash
# macOS/Linux, from the repository root
backend/.venv/bin/python scripts/verify.py
```

For real database tests, use a separate `*_test` database and `TOPH_TEST_RESET=YES`, as explained in the README, or let the included GitHub Actions workflow create an isolated PostGIS service. A skipped database suite does not count as a pass.

## 2. Configure live services

Configure these values privately, not in the chat or source files:

| Service | Required action | Where to put its configuration |
|---|---|---|
| Supabase/PostgreSQL | Rotate the shared password, enable PostGIS, run Alembic, create the restricted runtime role, and bootstrap a real farm/admin. | Runtime URL and extension schema in backend environment; migration URL stays with the operator. |
| AWS S3 | Create a private versioned general-purpose bucket. Apply `docs/aws-iam-policy.json` and `docs/s3-cors.json` after replacing their placeholders. | Backend AWS key/secret, region, and bucket name. |
| OpenAI | Set a project key, enabled Realtime/input-transcription/structured-extraction model IDs, and spending limits. | Backend environment only. |
| Satellite map | Obtain a licensed MapLibre-compatible satellite style JSON URL and restricted public browser token as required. | `VITE_MAP_STYLE_URL` in frontend environment. |

The S3 policy uses `s3:GetObject` for HEAD authorization and includes `s3:GetObjectVersion`. Keep versioning enabled, Block Public Access enabled, and avoid noncurrent-version expiration for pinned recordings.

Local live integration values go in `backend/.env` and `frontend/.env`. Restart the corresponding server after editing. Verify one real worker recording locally. Seed report audio is deliberately unavailable.

## 3. Put the repository on GitHub

After a successful `npm install`, keep the generated `frontend/package-lock.json`.

```bash
git init
git add .
git status
```

Confirm that no real `.env`, password, provider key, or local recording is staged. Then:

```bash
git commit -m "Implement TOPH"
git branch -M main
git remote add origin <YOUR-EMPTY-GITHUB-REPOSITORY-URL>
git push -u origin main
```

Open GitHub Actions and review the `TOPH checks` result. This workflow runs real PostGIS tests, frontend checks/build, and Chromium smoke tests. Browser evidence and the frontend lockfile are saved as artifacts. The workflow was included but could not be executed in the delivery runtime.

## 4. Set up production database and admin

Use separate production configuration and operator credentials. From `backend/`, with the virtual environment active and the production operator environment loaded:

```bash
python -m alembic upgrade head
```

From the root:

```bash
python scripts/create_runtime_role.py
```

Then from `backend/`:

```bash
python -m app.cli create-farm
```

Choose your actual farm name/timezone and admin credentials. Use `APP_ENV=production`. Never run the development seed in production. Keep `MIGRATION_DATABASE_URL` out of Vercel runtime variables. Full restricted-role and SSL instructions are in README section 6.

## 5. Create two Vercel projects

Import the same GitHub repository twice:

**Backend:** root `backend`, FastAPI, entry point `app/main.py` / `app.main:app`. Set the backend production variables:

```dotenv
APP_ENV=production
DATABASE_URL=<restricted pooled runtime URL>
POSTGIS_SCHEMA=<actual extension schema>
APP_ORIGINS=["https://YOUR-FRONTEND.vercel.app"]
COOKIE_SECURE=true
CSRF_SECRET=<independent random secret>
RATE_LIMIT_SECRET=<another independent random secret>
AWS_REGION=<bucket region>
AWS_ACCESS_KEY_ID=<restricted application access key>
AWS_SECRET_ACCESS_KEY=<application secret>
S3_BUCKET=<private versioned bucket name>
OPENAI_API_KEY=<project key>
OPENAI_REALTIME_MODEL=<enabled Realtime model ID>
OPENAI_TRANSCRIPTION_MODEL=<enabled transcription model ID>
OPENAI_EXTRACT_MODEL=<enabled Structured Outputs model ID>
```

Generate each server secret separately:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Frontend:** root `frontend`, Vite, Node 22, build `npm run build`, output `dist`. Set:

```dotenv
VITE_API_BASE_URL=/api/v1
VITE_MAP_STYLE_URL=<licensed satellite style JSON URL>
```

Deploy the backend and copy its stable production origin. Configure the rewrite from the repository root:

```bash
python scripts/set_backend_origin.py https://YOUR-FASTAPI-PROJECT.vercel.app
git add frontend/vercel.json
git commit -m "Set production API origin"
git push
```

Deploy/redeploy the frontend. Make backend `APP_ORIGINS`, S3 CORS, and the map token restrictions match the exact frontend origin. Redeploy after environment-variable changes. API rewrite comes before the SPA fallback. Resolve Vercel deployment protection without removing the application's authentication.

## 6. Run the release checks

With the virtual environment Python:

```bash
python scripts/smoke.py https://YOUR-FRONTEND.vercel.app
```

Enter the actual admin credentials privately. This checks login/logout, cookie forwarding, API JSON errors, data reads, cache headers, and route refresh through the real frontend.

Then complete one real recording on an actual phone. Confirm both voices are audible, activity/fertilizer/field values are correct, upload succeeds, playback and seeking work, and a retry does not duplicate the report. Repeat on iPhone Safari and Android Chrome for the stated browser support. Test using a dedicated test farm, not important employee data.

**Release gate:** a green build and real database tests, successful deployed smoke test, and successful live recording/upload/playback checks. The ZIP alone does not establish those results.
