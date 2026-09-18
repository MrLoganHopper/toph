# Farm Voice Reporting App
## Backend, database, and bare-bones frontend implementation specification

**Version:** 1.1 draft  
**Prepared:** September 17, 2026  
**Purpose:** A concrete implementation handoff for a separate FastAPI backend, relational database, and minimal admin/worker web interface. This package is a specification, not a deployed or tested application.

The requirements below are proposed product and implementation decisions. Provider capabilities are referenced using [S1], [S2], and so on. The sources are listed at the end.

# 1. Scope and fixed decisions

Build one modular FastAPI application and one React application. Use one PostgreSQL database with PostGIS and private object storage for audio. Keep the backend separate from the frontend, even when both deploy to Vercel.

The only account roles are `admin` and `worker`. A farm can have several admins. An account can have a membership in more than one farm. Authentication identifies a person; a checked farm membership determines access.

Activities are names of task types, such as Watering, Spraying, and Harvesting. Fertilizers are a parallel farm catalog with the same behavior and lifecycle rules as activities, for example Nitrogen 28-0-0 or Compost. Neither catalog has completion, active, or archive state. Anywhere the application accepts, returns, filters, schedules, extracts, or displays an activity, it must support a fertilizer alongside it with equivalent CRUD and authorization behavior. Shifts contain scheduled start and end timestamps only. Interview questions live in versioned Python source files, with the farm's field, activity, and fertilizer vocabulary inserted at runtime.

Included features:
- Admin dashboard, searchable log list, expandable report detail, audio playback, tags, and satellite field map.
- Account provisioning, memberships, simple field/activity/fertilizer settings, and planned shift scheduling.
- Minimal worker home, voice interview, upload, submission confirmation, and personal report history.
- Username/password authentication, tenant isolation, retry protection, migrations, seed data, and tests.

Excluded from this version:
- Microservices, queues, durable background jobs, and application WebSocket/SSE subscriptions.
- Actual clock-in/out, attendance confirmation, shift status, payroll, and live worker location.
- Log processing status, review/approval status, audit workflows, messages, read tracking, and unread/new counters.
- Reports exports, employee performance scoring, native mobile apps, and full offline synchronization.
- A database-managed interview/question editor and public self-service farm signup.

Do not add placeholder backend tables or endpoints for excluded features. Hide their sidebar entries rather than shipping nonfunctional controls.

# 2. Stack and deployment

| Layer | Selected implementation |
|---|---|
| Frontend | React, TypeScript, Vite, React Router, TanStack Query |
| UI | Geist font; simple reusable components and CSS or Tailwind; keep components replaceable |
| Backend | FastAPI, Pydantic, SQLAlchemy 2, psycopg 3 |
| Spatial integration | GeoAlchemy2 plus PostGIS |
| Migrations | Alembic |
| Database hosting | Managed PostgreSQL on Supabase, using its PostGIS extension |
| Audio | A private, versioned AWS S3 bucket |
| Voice interview | Browser-to-OpenAI Realtime connection using WebRTC |
| Structured extraction | Separate server-side OpenAI structured-output request |
| Map | MapLibre GL JS with a configured, licensed satellite tile/style provider |
| Repository | One GitHub repository, separate `frontend/` and `backend/` directories |
| Hosting | Two Vercel projects connected to the same repository |

Vercel documents native FastAPI deployment as a Python function and supports selecting different root directories for projects in one repository. The proposed backend remains independent; the frontend contains no business API. [S1][S2]

Supabase is being used as managed PostgreSQL here, not as a second authentication system. Its PostGIS extension and serverless connection options fit the selected architecture. [S5][S6]

```text
Desktop admin browser                 Worker mobile browser
          |                                      |
          +------------ React frontend ----------+
                            |
                       /api/v1/*
                            |
                  Vercel external rewrite
                            |
                 Separate FastAPI backend
                   /          |          \
          PostgreSQL       Private S3     OpenAI extraction
           + PostGIS

Worker browser ------ WebRTC ------ OpenAI Realtime
Worker browser ------ upload ------ Private S3
Admin browser ------- playback ---- Short-lived S3 download URL
```

The Vercel rewrite places the API under the frontend's browser origin while forwarding requests to a separate backend project. It is routing, not a second backend. Vercel documents this reverse-proxy behavior. [S3]


## 2.1 UI foundation and design-system handoff

The product font is **Geist**. Use Geist consistently across the admin and worker interfaces. Load it through a package or documented web-font integration; do not commit font binaries to the repository. Define the font once at the application root and inherit it throughout the UI.

The coding handoff will include Figma screenshots. Treat those screenshots as the visual source of truth for layout, spacing, hierarchy, component proportions, responsive behavior, and states. The implementation must create reusable design tokens/components rather than hardcoding each screenshot independently.

Before implementation, extract and centralize at least these tokens from the supplied designs: typography scale, font weights, colors, spacing, border radii, shadows, control heights, sidebar dimensions, content max widths, and responsive breakpoints. If a token cannot be inferred, choose one consistent value and document it rather than inventing different values per screen.

Motion should feel smooth and restrained. Implement hover/focus transitions, drawer/modal transitions, map-panel transitions, skeleton/loading states, and route-level state changes where shown by the handoff. Respect `prefers-reduced-motion`. Do not let animation block interaction or data loading.

## 2.2 Required visual/interaction handoff

The owner intends to provide Figma screenshots together with this specification. To maximize one-pass implementation quality, the coding agent should map each screenshot to a route and state before building. Prefer screenshot names such as `A03-dashboard.png`, `A06-map-field-selected.png`, `W04-recording-active.png`.

For every major screen, implement or deliberately account for these states even if only the primary layout is pictured: normal/data, loading/skeleton, empty, recoverable error, success/confirmation, and any modal/drawer/selected state relevant to that screen. Worker recording additionally needs ready, actively recording, uploading, generating, completed, failed/retry, and permission-denied states.

Interaction notes supplied with the Figma handoff override generic motion defaults. They should specify which interactions navigate, open a modal, open a drawer/side panel, expand inline, or remain on the same route; hover/focus/pressed behavior; and any desired transition direction/duration/easing. If exact animation numbers are absent, use a consistent restrained system and document it instead of varying animation behavior ad hoc.

Do not wait for perfect design coverage before implementing core behavior. Missing visual states should inherit the same design tokens/components and remain consistent with the supplied screens.

## Important hosting boundaries

Audio files go directly to S3. Never upload audio through FastAPI or a Vercel function. Vercel currently documents a 4.5 MB function request/response payload limit and bounded request durations. [S4]

Use a 60-second backend function duration for this version, a 50-second overall application deadline, and a 45-second maximum extraction request timeout. Disable automatic SDK retries on this path so they cannot multiply the request budget. Treat those as initial engineering limits to test, not measured performance guarantees. Keep requests and responses under the platform limits.

The live voice connection runs between the browser and the voice provider. FastAPI performs the short credential-creation request and the later structured-report request. It does not keep an HTTP request open for the entire conversation.

No task may be assumed to continue after an HTTP response. Do not use FastAPI `BackgroundTasks`, an in-memory queue, or an unawaited coroutine for essential report creation.

# 3. Authentication and onboarding

## 3.1 Login experience

Use one login screen with:

```text
Username
Password
Log in
```

No farm code is needed at login. Usernames are globally unique and normalized to lowercase. An example is `isaac.wang`. Names need not be unique.

After login:
1. Require a password change when using a temporary password.
2. A user with one enabled membership enters that farm directly.
3. A user with multiple enabled memberships sees a farm picker.
4. An admin enters the dashboard. A worker enters the worker home.

## 3.2 Creating the first accounts

Chosen v1 default: an operator CLI command creates a farm and its first admin atomically. It prompts for the password rather than putting it in shell history.

```bash
cd backend
python -m app.cli create-farm
```

An existing farm admin creates additional workers and admins in the Employees screen. The create-member endpoint creates a new global user plus a membership in the current farm. It generates a temporary password and returns it once. The administrator gives that credential to the person outside the app.

Do not silently attach an existing global username to the farm. Return `409 USERNAME_TAKEN`. A privileged operator CLI can explicitly attach an existing account to another farm. That prevents an admin from claiming another farm's existing account through a username match.

No email service, invitation table, farm code, or public registration endpoint is required in v1.

## 3.3 Password and session implementation

Use a maintained password library with Argon2id. FastAPI's security documentation demonstrates maintained password-hashing utilities, including `pwdlib`; do not invent a hash construction. [S7]

Product defaults:
- Usernames: 3 to 40 characters; lowercase letters, numbers, `.`, `_`, and `-`.
- Passwords: 12 to 128 characters. Permit password-manager paste. Do not silently trim a password.
- Temporary passwords: generate a high-entropy random value; never store plaintext.
- Session lifetime: 12 hours, with an absolute server-side expiry.
- Successful login creates a fresh cryptographically random token of at least 32 bytes.
- Store only `SHA-256(token)` in `auth_sessions`.
- The browser receives the raw token in an HttpOnly, Secure, SameSite=Lax, host-only cookie.
- Production cookie name: `__Host-farm_session`; `Path=/`; omit `Domain`.
- Local HTTP development uses a separate unprefixed cookie with `Secure=false`.
- Logout deletes the session and clears the cookie.
- Password change/reset revokes existing sessions. A successful self-change can issue a fresh session.

Opaque session cookies and revocation are the selected design, not a requirement to use JWT. Follow established session and CSRF practices. [S8][S9]

Keep auth tokens out of localStorage and frontend environment variables. The UI uses `credentials: "same-origin"` on the relative API path.

For authenticated mutations, require `X-CSRF-Token`. Derive that value using an HMAC of the session token with a server-only CSRF secret; return it through login and `/me`, and keep it in frontend memory. Verify it in constant time. Also validate the `Origin` against an exact environment-specific allowlist. The login endpoint validates Origin even though it has no authenticated CSRF token yet. Reject unsupported content types and unknown request fields.

Do not allow every `*.vercel.app` origin. Preview environments must have their own explicit origins and data isolation. No credentialed wildcard CORS.

## 3.4 Farm authorization

Every farm route resolves this context:

```text
valid session
  -> enabled user
  -> requested farm ID from route
  -> enabled membership for that user and farm
  -> role permission
  -> farm-scoped resource query
```

A farm ID is an identifier, not a credential. Changing a path or request body never grants access.

Use `get_current_user`, `require_farm_member`, and `require_farm_admin` dependencies. Even nested routes must include `farm_id` in the resource query. Cross-farm resource IDs return a generic 404. Unauthenticated requests return 401; insufficient role within an accessible farm returns 403.

A worker can read their own logs, recordings, and shifts. A worker can read the farm's field/activity/fertilizer vocabulary needed for reporting. They cannot list other workers, administer accounts, edit schedules, or access the admin dashboard.

Do not cache a role in a browser token as the authority. Read current membership state so disabling a worker takes effect on subsequent requests.

## 3.5 Account changes and recovery

Prevent disabling or demoting the last enabled admin in a farm. Lock the farm row in the transaction before checking this rule so simultaneous changes cannot remove every admin.

The admin password-reset endpoint only resets a worker account whose memberships are confined to the current farm and which has no admin membership. It returns a fresh temporary password, forces a change, and revokes sessions.

Resetting an admin or a shared account requires the operator CLI in v1. A farm admin must not reset a global identity that has privileged or unrelated memberships elsewhere.

A user changing their own password must supply the current password. During a required temporary-password change, only `/me`, logout, and the change-password route are available.

## 3.6 Rate limits

Use the shared `rate_limit_buckets` table to avoid instance-local counters on serverless hosting. Increment with one atomic upsert.

Initial configurable limits:
- Login: 10 attempts per username-plus-trusted-IP per 15-minute window, with a broader IP limit.
- Realtime credentials: 10 per user per hour.
- Recording initialization and log generation: 30 per user per hour.
- Account creation and password reset: 20 per admin per hour.

Include the policy name and farm/user subject in the HMAC key where appropriate. A limit returns 429 with `Retry-After`. Only trust client-IP headers supplied through a verified deployment proxy configuration. Do not accept arbitrary client-provided forwarding headers as authority.

These are starting abuse controls, not a complete security assessment. Test auth, authorization, and recovery before using real employee data.

# 4. Database contract

The complete column dictionary, constraints, and examples are in `database_schema.json`. Concrete illustrative rows are in `example_records.json`. These files are readable schema documents, not executable migrations or formal JSON Schema.

Use an application schema named `farm_app`. Keep it out of the Supabase public Data API's exposed schemas. Revoke access from public/anonymous application roles, use an appropriately restricted backend database role, and use separate migration credentials. The browser never receives a database password or elevated provider key.

API authorization protects reads. Composite foreign keys protect relationships. One does not replace the other.

Use UUID primary keys, UTC-aware `timestamptz`, and an IANA timezone on the farm. PostgreSQL's timezone-aware timestamp behavior supports storing instants separately from the display timezone. [S16]

## 4.1 All table shapes in JSON

The following strings describe types. `null` is allowed only where explicitly shown. Timestamp fields default to the server's current time unless supplied for recorded or scheduled times. `updated_at` must be updated by the application; its initial default alone is insufficient.


```json
{
  "farms": {
    "id": "uuid (primary key)",
    "name": "varchar(120)",
    "timezone": "IANA timezone string",
    "created_at": "timestamptz",
    "updated_at": "timestamptz"
  },
  "users": {
    "id": "uuid (primary key)",
    "username": "varchar(40), globally unique, lowercase",
    "name": "varchar(120)",
    "password_hash": "text (Argon2id, never returned)",
    "must_change_password": "boolean",
    "is_enabled": "boolean",
    "created_at": "timestamptz",
    "updated_at": "timestamptz"
  },
  "farm_memberships": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "user_id": "uuid -> users.id",
    "role": "admin | worker",
    "is_enabled": "boolean",
    "created_at": "timestamptz",
    "updated_at": "timestamptz"
  },
  "auth_sessions": {
    "id": "uuid (primary key)",
    "user_id": "uuid -> users.id",
    "token_hash": "char(64), unique",
    "created_at": "timestamptz",
    "expires_at": "timestamptz"
  },
  "fields": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "name": "varchar(120)",
    "geometry": "PostGIS geometry(MULTIPOLYGON, 4326)",
    "created_at": "timestamptz",
    "updated_at": "timestamptz"
  },
  "activities": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "name": "varchar(100)",
    "created_at": "timestamptz",
    "updated_at": "timestamptz"
  },
  "fertilizers": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "name": "varchar(100)",
    "created_at": "timestamptz",
    "updated_at": "timestamptz"
  },
  "shifts": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "employee_id": "uuid -> users.id; must have a membership in this farm",
    "field_id": "uuid -> fields.id | null",
    "activity_id": "uuid -> activities.id | null",
    "fertilizer_id": "uuid -> fertilizers.id | null",
    "start_at": "timestamptz (scheduled)",
    "end_at": "timestamptz (scheduled)",
    "created_at": "timestamptz",
    "updated_at": "timestamptz"
  },
  "recordings": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "employee_id": "uuid -> users.id; must have a membership in this farm",
    "client_submission_id": "uuid, created on phone for safe retries",
    "payload_hash": "char(64), server-computed canonical metadata hash",
    "object_key": "text, server-generated private storage key",
    "object_version_id": "text | null, pinned S3 version after upload verification",
    "content_type": "varchar(100)",
    "size_bytes": "bigint",
    "duration_ms": "integer",
    "transcript": "jsonb array of {speaker: assistant|worker, text: string, offset_ms: integer}",
    "waveform_peaks": "jsonb array of finite numbers 0..1 | null",
    "interview_version": "varchar(40), version string for questions stored in code",
    "recorded_at": "timestamptz (client-reported capture start)",
    "uploaded_at": "timestamptz | null",
    "created_at": "timestamptz"
  },
  "logs": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "employee_id": "uuid -> users.id; copied from recording by server",
    "recording_id": "uuid -> recordings.id, unique",
    "shift_id": "uuid -> shifts.id | null",
    "field_id": "uuid -> fields.id | null",
    "activity_id": "uuid -> activities.id | null",
    "fertilizer_id": "uuid -> fertilizers.id | null",
    "summary": "text",
    "answers": "jsonb object {details: string|null, issues: string|null}",
    "extraction_confidence": "numeric(5,4) 0..1 | null (model estimate)",
    "extractor_model": "varchar(100)",
    "extraction_version": "varchar(40)",
    "submission_hash": "char(64), hash of recording_id and explicit shift_id",
    "recorded_at": "timestamptz, copied from recording by server",
    "created_at": "timestamptz"
  },
  "tags": {
    "id": "uuid (primary key)",
    "farm_id": "uuid -> farms.id",
    "name": "varchar(80)",
    "created_at": "timestamptz"
  },
  "log_tags": {
    "farm_id": "uuid",
    "log_id": "uuid -> logs.id",
    "tag_id": "uuid -> tags.id",
    "created_at": "timestamptz"
  },
  "rate_limit_buckets": {
    "key_hash": "char(64), HMAC of policy and subject",
    "bucket_start": "timestamptz",
    "request_count": "integer",
    "expires_at": "timestamptz"
  }
}
```

## 4.2 Relationships

```text
farms --< farm_memberships >-- users --< auth_sessions
  |
  +--< fields
  +--< activities
  +--< fertilizers
  +--< shifts >-- employee membership
  +--< recordings >-- employee membership
  +--< logs >-- recording, optional shift, optional field/activity/fertilizer
  +--< tags

logs --< log_tags >-- tags
```

There are 13 application tables. `auth_sessions` and `rate_limit_buckets` are small authentication infrastructure tables. Alembic also creates its own migration-version table.

Do not put `logs: [id]`, `shifts: [id]`, `fields: [id]`, `activities: [id]`, or `fertilizers: [id]` on parent rows. Query related records through their foreign keys.

A transcript, numeric waveform, or fixed-shape answer document can reasonably be JSONB. Those are document values, not a substitute for relational foreign keys.

## 4.3 Required database constraints

Implement every constraint in the dictionary, plus these cross-table rules:

- `farm_memberships`: unique `(farm_id, user_id)` and `(farm_id, id)`.
- Each tenant resource used by a composite FK has unique `(farm_id, id)`.
- `shifts` and `recordings` additionally have unique `(farm_id, id, employee_id)`.
- `logs(farm_id, recording_id, employee_id)` references the corresponding recording triple.
- `logs(farm_id, shift_id, employee_id)` references the corresponding shift triple.
- Field/activity/fertilizer/tag references include `farm_id`; a report in Farm A cannot point at a field in Farm B.
- `logs.recording_id` is unique. One recording creates at most one report in v1.
- Recording initialization is unique on `(farm_id, employee_id, client_submission_id)`.
- Field, activity, fertilizer, and tag names are case-insensitively unique within a farm.

Nullable compound references use standard `MATCH SIMPLE`. Keep historical memberships rather than deleting them. Default deletion of referenced business records is restricted. Account removal is membership disabling. Deleting a referenced field, activity, fertilizer, or shift returns 409.

Tag attachment uses the composite primary key `(farm_id, log_id, tag_id)`, making repeat attachment harmless.

## 4.4 Indexes

Create these initial log indexes:

```text
(farm_id, recorded_at DESC, id DESC)
(farm_id, employee_id, recorded_at DESC, id DESC)
(farm_id, field_id, recorded_at DESC, id DESC)
(farm_id, activity_id, recorded_at DESC, id DESC)
(farm_id, fertilizer_id, recorded_at DESC, id DESC)
```

Also index membership user lookups, session expiry/user, recording timestamp, scheduled employee/time, reverse tag lookups, and rate-limit expiry. Use a GiST spatial index for field geometry.

Start search with parameterized SQL against joined names, summaries, and tags. Add a measured trigram/full-text optimization later if query plans justify it. No dedicated search service is required by this spec.

## 4.5 Important semantics

`recordings.recorded_at` is the client-reported recording start. `recordings.uploaded_at` means the storage upload was verified. `logs.created_at` is when the structured report was committed. These are different timestamps.

`logs.recorded_at` is a deliberate copy from its immutable recording for indexed report queries. Only the backend sets it.

`uploaded_at` and `object_version_id` are storage receipt metadata. They do not introduce an AI processing workflow or status enum.

`shift.start_at` and `shift.end_at` are scheduled times. The detail UI labels them as scheduled. Without a linked shift, display “No linked shift.” Do not fabricate a time range from the recording duration.

The report schema supports one field, one activity, and one fertilizer per recording in v1. The interview should ask workers to submit separate reports for materially different field/activity/fertilizer combinations. If no single field/activity/fertilizer is supported by the worker's answer, save null and retain the detail in the transcript and summary. Never silently select the first ID.

Questions remain in code. `interview_version` and `extraction_version` are short version identifiers, not saved question sets.


# 5. API conventions and endpoint inventory

FastAPI is the single source of business validation. Use Pydantic request/response classes with explicit safe output models. Generate the real OpenAPI document from the application and optionally generate frontend TypeScript types from it.

Use snake_case in JSON. UUIDs are JSON strings. Every datetime input must include an offset; return datetimes in RFC 3339 UTC form. All mutations have the CSRF requirement from section 3 even when the compact table says only “admin” or “member.”

All authenticated responses, including signed URLs and login/bootstrap responses, use `Cache-Control: private, no-store`. Configure CDN caching headers consistently so a Vercel rewrite never shares farm data between users. [S3]

Conventional response rules:
- 200: successful read/update or idempotent replay.
- 201: newly created resource.
- 204: successful action with no response body.
- 401: invalid/missing/expired authentication.
- 403: known farm membership but insufficient permission.
- 404: missing or inaccessible cross-farm resource.
- 409: uniqueness conflict, protected historical reference, unsafe account change, or conflicting retry.
- 413: application request limit exceeded.
- 422: invalid input, invalid geometry, missing transcript, or audio not uploaded.
- 429: rate limit.
- 502: external service failure/refusal/invalid structured output.
- 504: bounded extraction timeout.

Standard errors use:

```json
{
  "error": {
    "code": "EXTRACTION_TIMEOUT",
    "message": "Your recording is saved. Try creating the report again.",
    "retryable": true,
    "request_id": "server-generated-request-id"
  }
}
```

Normalize validation errors into this envelope. Do not expose stack traces, SQL, provider keys, or raw provider responses. Do not put recordings or transcripts in URL query strings.

In the table below, `F` means `/api/v1/farms/{farm_id}`.

| Method | Path | Permission | Function and inputs | Output |
|---|---|---|---|---|
| GET | `/healthz` | public | Liveness check without sensitive configuration. Input: none | {"ok":true} (200) |
| POST | `/api/v1/auth/login` | public; Origin checked | Verify credentials and issue a new cookie session. Input: LoginInput: username, password | AuthResult: safe user, enabled memberships with farm summaries, csrf_token, password-change requirement; Set-Cookie header (200) |
| GET | `/api/v1/me` | authenticated | Restore frontend identity and current memberships. Input: session cookie | AuthResult; no password hash or raw session token (200) |
| POST | `/api/v1/auth/logout` | authenticated + CSRF | Revoke current session and clear cookie. Input: empty body | no body (204) |
| POST | `/api/v1/auth/change-password` | authenticated + CSRF | Verify current password; change hash; revoke old sessions and rotate current one. Input: current_password, new_password | AuthResult and replacement session cookie (200) |
| GET | `F` | member | Read current farm. Input: path farm_id | Farm: id, name, timezone, created_at, updated_at (200) |
| PATCH | `F` | admin | Edit farm name/timezone. Input: name and/or timezone | updated Farm (200) |
| GET | `F/bootstrap` | member | Load role-specific initialization data. Input: optional local_date YYYY-MM-DD; defaults to farm-local today | user, farm, membership, fields, activities, fertilizers, own scheduled shifts; admins also get worker filter options and tags (200) |
| GET | `F/members` | admin | List employees and admins. Input: role?, enabled?, q?, cursor?, limit 1..100 | Page<Member>: user id/name/username, membership id/role/enabled (200) |
| POST | `F/members` | admin | Create a new user and farm membership atomically. Input: name, username, role admin / worker | safe Member and temporary_password returned once (201) |
| PATCH | `F/members/{membership_id}` | admin | Change role or farm access; protect last admin. Input: role? and/or is_enabled? | updated Member (200) |
| POST | `F/members/{membership_id}/reset-password` | admin | Reset an eligible farm-confined worker account. Input: empty body | temporary_password and must_change_password:true, returned once (200) |
| GET | `F/fields` | member | List field metadata for settings and selection. Input: cursor?, limit 1..100 | Page<FieldSummary>: id, name (200) |
| GET | `F/fields/geojson` | member | Load field polygons for maps. Input: cursor?, limit 1..50; optional field_id | GeoJSON FeatureCollection with next_cursor; top-level farm_bbox (200) |
| GET | `F/fields/{field_id}` | member | Read one field including boundary. Input: path field_id | Field with GeoJSON geometry (200) |
| POST | `F/fields` | admin | Create field from supplied boundary. Input: name, geometry: Polygon or MultiPolygon GeoJSON | Field with normalized MultiPolygon (201) |
| PATCH | `F/fields/{field_id}` | admin | Edit field name and/or geometry. Input: name?, geometry? | updated Field (200) |
| DELETE | `F/fields/{field_id}` | admin | Delete only an unreferenced field. Input: path field_id | no body; 409 if referenced (204) |
| GET | `F/activities` | member | List task vocabulary. Input: cursor?, limit 1..100 | Page<Activity>: id, name (200) |
| POST | `F/activities` | admin | Create task type, not a scheduled task instance. Input: name | Activity (201) |
| PATCH | `F/activities/{activity_id}` | admin | Rename a task type. Input: name | Activity (200) |
| DELETE | `F/activities/{activity_id}` | admin | Delete only an unreferenced task type. Input: path activity_id | no body; 409 if referenced (204) |
| GET | `F/fertilizers` | member | List fertilizer vocabulary. Input: cursor?, limit 1..100 | Page<Fertilizer>: id, name (200) |
| POST | `F/fertilizers` | admin | Create fertilizer category/product. Input: name | Fertilizer (201) |
| PATCH | `F/fertilizers/{fertilizer_id}` | admin | Rename a fertilizer category/product. Input: name | Fertilizer (200) |
| DELETE | `F/fertilizers/{fertilizer_id}` | admin | Delete only an unreferenced fertilizer category/product. Input: path fertilizer_id | no body; 409 if referenced (204) |
| GET | `F/shifts` | member; workers self-only | Read planned schedule with interval-overlap filtering. Input: from, to, employee_id?, cursor?, limit 1..100 | Page<Shift>: planned start/end, employee, optional field/activity/fertilizer (200) |
| POST | `F/shifts` | admin | Create a scheduled assignment. Input: employee_id, start_at, end_at, field_id:null / UUID, activity_id:null / UUID, fertilizer_id:null / UUID | Shift (201) |
| PATCH | `F/shifts/{shift_id}` | admin | Edit planned assignment; preserve referenced identity. Input: start_at?, end_at?, field_id?, activity_id?, fertilizer_id?; employee_id change only if unreferenced | Shift (200) |
| DELETE | `F/shifts/{shift_id}` | admin | Delete an unreferenced scheduled assignment. Input: path shift_id | no body; 409 if linked to a log (204) |
| POST | `F/realtime/client-secret` | member | Mint short-lived voice credential using fixed server instructions. Input: optional own shift_id; no arbitrary model/instructions | client_secret, expires_at, configured model, interview_version; no permanent provider key (200) |
| POST | `F/recordings` | member; own recording | Persist immutable recording metadata and transcript before AI work. Input: RecordingInput; client_submission_id required | RecordingReceipt: id, recorded_at, uploaded_at, linked_log_id; 200 on identical retry (201 or 200) |
| GET | `F/recordings/{recording_id}` | admin or owning worker | Recover recording receipt/details after interrupted submission. Input: path recording_id | RecordingDetail, including transcript and computed linked_log_id (200) |
| POST | `F/recordings/{recording_id}/upload-url` | owning member | Create or renew restricted direct-upload authorization. Input: empty body; reject if already confirmed | url, method:POST, fields, expires_at, max_size_bytes (200) |
| POST | `F/recordings/{recording_id}/complete` | owning member | Verify S3 object, pin version, and record upload receipt. Input: empty body | RecordingReceipt with uploaded_at set; repeat is safe (200) |
| POST | `F/logs` | admin or owning worker | Synchronously generate and persist a report from a confirmed recording. Input: recording_id, shift_id:null / UUID | LogDetail; 201 new, 200 identical retry; never 202 (201 or 200) |
| GET | `F/logs` | admin or worker self-only | Reusable filtered query for dashboard, activity/fertilizer grid, map sidebar, and history. Input: LogFilters, cursor?, limit 1..100 | Page<LogListItem> with total_matching and next_cursor (200) |
| GET | `F/logs/{log_id}` | admin or owning worker | Read full report without creating a view/read event. Input: path log_id | LogDetail with summary, answers, transcript, recording metadata, tags, field geometry, and scheduled shift (200) |
| GET | `F/logs/{log_id}/audio-url` | admin or owning worker | Authorize temporary browser playback of the pinned private recording. Input: path log_id | url, expires_at, content_type, duration_ms (200) |
| GET | `F/dashboard` | admin | Return explicit dashboard metrics and the first filtered report page. Input: LogFilters; no cursor; initial limit default 25 | DashboardResult: as_of, timezone, metrics, metric_scopes, logs (200) |
| GET | `F/tags` | member | Read farm tag catalog. Input: cursor?, limit 1..100 | Page<Tag>: id, name (200) |
| POST | `F/tags` | admin | Create a tag. Input: name | Tag; duplicate same-farm name returns 409 (201) |
| PUT | `F/logs/{log_id}/tags/{tag_id}` | admin | Attach an existing same-farm tag idempotently. Input: empty body | updated list of tags on the log (200) |
| DELETE | `F/logs/{log_id}/tags/{tag_id}` | admin | Remove tag attachment idempotently. Input: empty body | no body (204) |


Static routes such as `/fields/geojson` must be registered before `/{field_id}`. Workers passing another employee's ID to a self-only endpoint must not broaden the query. Do not add a separate “active shifts” endpoint, because this version only has schedules.

## 5.1 RecordingInput

```json
{
  "client_submission_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "content_type": "audio/webm",
  "size_bytes": 640000,
  "duration_ms": 81000,
  "recorded_at": "2026-09-17T13:02:00Z",
  "interview_version": "interview-v1",
  "transcript": [
    {
      "speaker": "assistant",
      "text": "What work did you complete, and where?",
      "offset_ms": 0
    },
    {
      "speaker": "worker",
      "text": "I watered Field A with drip irrigation and noticed a leak.",
      "offset_ms": 4500
    }
  ],
  "waveform_peaks": [0.1, 0.24, 0.58, 0.74, 0.42, 0.18]
}
```

The server supplies the employee identity and farm context. The client never chooses an S3 object key or supplies an arbitrary recording URL. Validate the interview version, timestamp bounds, known speaker values, offset ranges, nonempty worker text, and maximum JSON body size.

Target recording limit: 10 minutes and 25 MiB. Target transcript/metadata request limit: 256 KiB. Accept supported audio containers from an explicit allowlist such as WebM, MP4, and Ogg. Normalize the content type consistently between the recorded blob and the storage policy.

## 5.2 Log creation input

```json
{
  "recording_id": "77777777-7777-4777-8777-777777777777",
  "shift_id": "66666666-6666-4666-8666-666666666666"
}
```

`shift_id` is an explicitly supplied nullable field. The worker UI can suggest a shift when exactly one scheduled interval covers the recording start; the worker can select a different appropriate own shift or leave it unlinked. Do not automatically choose one of multiple overlapping shifts.

The selected shift must have the same farm and employee as the recording. An admin retrying extraction for a worker's recording does not become that recording's employee.

## 5.3 LogFilters and pagination

Supported filters:

```text
range=today | this_week | this_month | all
from=<inclusive timezone-aware datetime>
to=<exclusive timezone-aware datetime>
employee_id=<UUID>
field_id=<UUID>
activity_id=<UUID>
fertilizer_id=<UUID>
tag_id=<UUID>
q=<plain search string, maximum 200 characters>
sort=recorded_at
direction=asc | desc
limit=1..100
cursor=<opaque validated cursor>
```

Use either `range` or explicit `from` and `to`, not both. If dates are explicit, both are required. The dashboard defaults to this month; the general log list defaults to all time. A week starts Monday in the farm's timezone.

Filters combine with AND. Within `q`, search is OR across employee name, field name, activity name, fertilizer name, summary, and tag names. Use one parameterized phrase search initially. Do not claim semantic or fuzzy search. Use `EXISTS` for tag matching to avoid duplicate log rows.

Use stable keyset pagination ordered by `(recorded_at, id)` in the selected direction. Fetch `limit + 1` to determine the next page. Encode the final ordering values and a filter fingerprint in the cursor. Validate it; reset pagination whenever filters or direction change. Do not use a timestamp alone as a cursor.

Response:

```json
{
  "items": [],
  "total_matching": 0,
  "next_cursor": null
}
```

A total covers all matching records, not only the current page. Normal page changes under concurrent inserts are acceptable for v1; do not claim a snapshot-consistent archive. All queries still apply the current user's access constraints.

Schedule filtering uses interval overlap, not the report timestamp predicate:

```text
shift.start_at < requested_to
AND shift.end_at > requested_from
```

## 5.4 LogListItem versus LogDetail

A list item includes:
- `id`, `recorded_at`, employee `{id,name}`, activity `{id,name}` or null, fertilizer `{id,name}` or null, and field `{id,name}` or null.
- Linked scheduled shift `{id,start_at,end_at}` or null.
- A short `summary_preview`, nullable `extraction_confidence`, and tags.

It does not include the full transcript, audio URL, waveform, or field geometry.

A detail adds the full summary, fixed-shape answers, recording duration/type/waveform/transcript, full selected-field GeoJSON, and the linked planned schedule. It still excludes storage credentials, internal hashes, and a permanent public audio URL.

Fetch the signed playback URL only when playback is requested. Expired playback URLs can be renewed after another authorization check.

## 5.5 Catalog and map pagination

Metadata catalogs use ordinary `items/next_cursor` envelopes. Bootstrap can assemble the small field/activity/fertilizer vocabulary across internal pages so workers receive the complete allowed vocabulary.

`fields/geojson` is a GeoJSON FeatureCollection with `next_cursor` and `farm_bbox` as additional members. Use up to 50 fields per page and up to 1,000 positions per field in v1; keep serialized responses below the Vercel payload ceiling. The map fetches all pages before fitting the complete farm view. Do not silently discard later fields.

`farm_bbox` is computed from all farm field geometries, not only the current page. With no fields, return an empty FeatureCollection, null bbox, and a useful UI empty state.


# 6. Voice, storage, and report creation

## 6.1 Interview prompts

Keep these modules in the backend:

```text
app/prompts/interview_v1.py
app/prompts/extraction_v1.py
```

The interview uses a fixed sequence:
1. Ask what activity the worker performed.
2. Ask which fertilizer they used, if any. The worker may explicitly answer none/not applicable.
3. Ask which field they worked in.
4. Ask for useful details of the work.
5. Ask whether there were problems or observations.

Insert the authorized farm's field/activity/fertilizer IDs and names and the farm-local date. A schedule can supply context, but it cannot establish what the worker actually did. Clarify an ambiguous field/activity/fertilizer instead of guessing. Ask about one main field/activity/fertilizer combination per report.

The AI must identify itself as the voice assistant. Display a clear recording indicator and tell the worker that audio is being saved. No hidden recording.

The browser receives a short-lived Realtime client secret from FastAPI. The permanent provider API key stays server-side. OpenAI documents this browser credential/WebRTC pattern. [S10]

## 6.2 Browser recording implementation

Implement a replaceable `useVoiceInterview` hook with a raw WebRTC transport or a supported transport adapter. The concrete v1 integration must expose the local microphone stream and remote assistant audio stream to the recorder.

Flow:
1. The worker taps Start. Request microphone permission through this user gesture.
2. Fetch a short-lived credential with server-configured instructions and model.
3. Connect the microphone to the provider through WebRTC.
4. Enable input transcription and collect final speaker-labelled transcript turns.
5. Record the combined local microphone and remote assistant output.
6. On Finish, wait for outstanding final transcript messages, stop recording, and save the completed draft locally.
7. Upload and generate the log using the HTTP pipeline below.

Recording only the microphone would omit the assistant from the saved conversation. Mix both audio sources into a `MediaStreamAudioDestinationNode`, then record that stream with MediaRecorder. Send only the microphone to the provider, not the mixed stream. Play remote audio through one output path to avoid doubling it. The Web Audio API provides the relevant stream destination primitive. [S14]

Use `MediaRecorder.isTypeSupported()` rather than hardcoding WebM. Detect the supported container, create the matching blob and content type, and test the result on target browsers. MDN documents this feature detection. [S15]

Build the waveform in the browser by sampling the mixed signal and downsampling amplitude values to approximately 256 peaks. Store those values with recording metadata. Peaks are decorative, client-reported presentation data; do not treat them as evidence of quality. A missing waveform must not block audio playback.

Target browsers: current desktop Chrome/Edge, Android Chrome, and iPhone Safari. Microphone permission, actual playback, seeking, tab suspension, and format compatibility need real-device testing. Keep the recording screen open during a call. This spec does not promise native-app background recording.

Keep completed drafts in IndexedDB under the current user and farm. Do not clear a draft until the server confirms the saved report. Clear sensitive drafts on explicit logout with a warning when there is an unsent recording. Do not display another account's draft on a shared device.

No full offline voice-agent mode is included. A lost network connection produces a visible recoverable error; a completed local draft can be retried. A browser crash during capture is not guaranteed to be recoverable in v1.

## 6.3 Upload and extraction sequence

```text
Finish interview and preserve local draft
  -> POST /recordings
       Save transcript/metadata with client_submission_id
  -> POST /recordings/{id}/upload-url
       Return a restricted S3 upload form
  -> Browser POSTs audio directly to S3
  -> POST /recordings/{id}/complete
       Verify upload and pin object version
  -> POST /logs
       Extract, validate, and commit the report
  -> 201 new report or 200 identical existing report
  -> Remove completed local draft
```

S3 presigned POST policies support constrained upload fields, size ranges, and expiry. Use an exact server-generated object key, a short expiry such as 10 minutes, an allowed content type, and `content-length-range`. Do not permit public ACL fields. [S11]

Enable bucket versioning. Confirmation performs a server-side HEAD on the expected key, verifies size/type, records `VersionId`, and sets `uploaded_at`. Future playback addresses that exact version. Presigned upload permissions can remain usable until expiry; pinning a version avoids a later overwrite changing a finalized recording's playback target. [S12][S13]

An identical confirmation retry returns the already pinned receipt without switching to a newer object version. Never accept a client-supplied bucket, key, public URL, or arbitrary external fetch target.

Configure storage CORS for exact frontend origins and the methods/headers actually needed for upload and playback. Expose relevant version, type, and range headers as required by the client. Storage requests do not carry the application's session cookie. Apply storage encryption and least-privilege credentials.

Before extraction, release the database session/transaction used to load context. Do not hold a connection and row locks while waiting for the model. After the model responds, open a short transaction, recheck authorization/references, and insert the log.

## 6.4 Structured extraction

The server loads:
- The persisted transcript, capture time, and interview version.
- The farm's current allowed field, activity, and fertilizer IDs/names.
- The explicitly selected, same-employee shift or null.

Use a strict structured-output model with a Pydantic schema matching this shape:

```json
{
  "summary": "Watered Field A and reported a leak in the irrigation line.",
  "field_id": "44444444-4444-4444-8444-444444444444",
  "activity_id": "55555555-5555-4555-8555-555555555555",
  "fertilizer_id": "99999999-9999-4999-8999-999999999991",
  "answers": {
    "details": "Watered using drip irrigation.",
    "issues": "Leak in the north irrigation line."
  },
  "extraction_confidence": 0.9
}
```

Every key is required, with nullable values for unknown field/activity/fertilizer/answers/confidence. Require a nonblank summary. Unknown information remains unknown. Do not create a new field, activity, or fertilizer from model output.

Validate types, limits, and exact same-farm IDs in application code even when the model follows a JSON schema. Structured Outputs constrain shape; they can still contain content mistakes. [S17]

Treat the transcript and farm vocabulary as untrusted data, never executable instructions. The extraction request gets no database tools and no ability to change authorization. Extract facts from worker utterances. Assistant suggestions, question wording, and the scheduled assignment are not proof of completed work.

The final log's employee, farm, recording, shift, and recorded_at are assigned by backend logic. The model cannot choose an employee, grant a role, select an arbitrary tenant, or write SQL.

The MVP accepts client-delivered transcripts and recording timestamps as self-reported submissions. It does not verify that the transcript matches the audio or make the report tamper-proof. Retaining both allows a person to listen and compare.

## 6.5 Safe retries without job statuses

At recording initialization, compute `payload_hash` from canonical immutable client metadata. Repeating the same client submission ID and metadata returns the same recording. Reusing that ID with a different payload returns 409.

At log creation, canonicalize `recording_id` and the explicit nullable `shift_id` into `submission_hash`. If the recording already has a log:
- Same submission hash: return the existing log with 200.
- Different submission hash: return 409 rather than silently modifying the report.

Otherwise call the extractor within a bounded HTTP request. Insert only after valid output exists. A database unique constraint on recording_id prevents two simultaneous retries from committing duplicate reports. On a duplicate-insert race, read the winning row and apply the same hash comparison.

This guarantees at most one saved log per recording. It does not guarantee at most one external model call under concurrent retries.

If extraction times out or fails, keep the confirmed audio and transcript and return an error with the recording ID. The frontend displays “Recording saved. Report generation failed. Try again.” The next attempt reuses that recording. Never ask the worker to record the entire conversation again merely because extraction failed.

There is no queue, processing-status column, 202 response, or invisible job. Loading/uploading/generating indicators are transient frontend state, not persisted workflow statuses.

## 6.6 Playback

```text
Admin opens a log
  -> GET /logs/{id}
       Summary, waveform, transcript, field geometry
Admin presses Play
  -> GET /logs/{id}/audio-url
       Recheck membership and log access
  -> Browser audio element fetches the private S3 version
```

Use an ordinary HTML audio element with controls, preload set conservatively, and a custom waveform wrapper. The backend returns a short-lived signed GET, such as five minutes, with a correct audio content type.

Seeking may require additional byte-range requests. When a signed URL expires, get a new one, restore the prior playhead, and allow retry. Test actual range/seek behavior against the chosen object store.

Do not send the audio through a FastAPI response. Do not store a signed URL in the database or cache it in a shared CDN.

# 7. Dashboard semantics

Three cards:
1. **Today's Recordings:** finalized reports whose recording date falls within today's interval in the farm timezone, counted once per recording. Saved audio without a successfully generated log is retained but excluded from this dashboard report metric.
2. **Scheduled Now:** distinct enabled workers whose planned shift satisfies `start_at <= as_of < end_at`. This is not attendance or proof of activity.
3. **Extraction Confidence:** mean of non-null model-estimated confidence across all logs matching the current dashboard filters. Show the number of included reports. Empty input displays “No data.”

Do not call the third metric “Response Accuracy.” No human-ground-truth workflow exists in this version. A model estimate must be labelled as an estimate.

Remove the “1 New” badge. Rename the table to “Recent Employee Logs.” Opening a report creates no database record.

The first two cards are farm-wide and unaffected by table search/filter changes. Confidence and the report count follow table filters. Make that scope explicit in tooltips and response metadata.

Example response:

```json
{
  "as_of": "2026-09-17T16:00:00Z",
  "timezone": "America/Los_Angeles",
  "metrics": {
    "recordings_today": 5,
    "scheduled_workers_now": 12,
    "average_extraction_confidence": null,
    "confidence_sample_size": 0
  },
  "metric_scopes": {
    "recordings_today": "farm_local_today",
    "scheduled_workers_now": "farm_schedule_at_as_of",
    "average_extraction_confidence": "all_matching_logs"
  },
  "logs": {
    "items": [],
    "total_matching": 0,
    "next_cursor": null
  }
}
```

The example card numbers are illustrative, not expected seed totals. For a test fixture, returned totals must match the actual fixture records.

Use a single captured server `as_of` for the time calculations. An empty table returns zero counts where appropriate and null confidence, never NaN.

Fetch on page load and provide Refresh. Optional 30-second dashboard polling while the tab is visible is sufficient. Do not introduce an app event bus or subscription service.

# 8. Screens and the data they display

| Route/screen | Data shown | Actions/API |
|---|---|---|
| `/login` | Username, password, generic auth error | Login |
| `/change-password` | Current/temporary password and new password | Self-change and session rotation |
| `/select-farm` | Enabled farm memberships, farm name, role | Select accessible farm; no authorization mutation |
| `/admin/:farmId/dashboard` | Three defined cards, search, filters, recent-log table | Bootstrap and dashboard; open log; refresh |
| `/admin/:farmId/logs` | Searchable, paginated grid with activity title, fertilizer, employee, field, recorded date, tags | Shared logs query; open detail |
| Log detail drawer/page | Summary, answers, full transcript, recorded date, employee, field, activity, fertilizer, scheduled time, waveform, audio | Detail, signed audio URL, add/remove tags, expand map |
| `/admin/:farmId/map` | Satellite basemap, farm polygons, selected field, latest ten field reports | GeoJSON pages and filtered logs |
| `/admin/:farmId/employees` | Names, usernames, membership roles, enabled state | Create account, change role/access, eligible worker password reset |
| `/admin/:farmId/schedule` | Planned worker assignments with field/activity/fertilizer and start/end | Shift list/create/edit/delete |
| `/admin/:farmId/settings` | Farm name/timezone, field definitions, activity vocabulary, fertilizer vocabulary, tag creation | Basic settings/catalog forms |
| `/worker/:farmId` | Worker name, farm, own scheduled shifts, recent own reports | Bootstrap and own logs |
| `/worker/:farmId/record` | Start/finish controls, live transcript, recording indicator, elapsed duration, retry/save result | Voice, recording, upload, and log pipeline |
| `/worker/:farmId/history` | Own reports and personal detail/playback | Same logs endpoints with backend self-scoping |

The admin sidebar only contains implemented pages: Dashboard, Activity Logs, Map, Employees, Schedule, and Settings. Account menu contains farm switch, password change, and logout.

Use query keys that include user ID, farm ID, and filters. Clear user-specific query caches on logout and farm/account changes. Frontend route guards are navigation aids; API permissions remain authoritative.

Store filter state in URL search parameters. Debounce search by approximately 300 ms, cancel superseded requests, and reset the cursor when a filter changes.

Detail components should be shared by dashboard, grid, history, and map rather than rewritten for each page. Lazy-load transcript/waveform/map data through detail calls. Keep forms functional with basic styling; visual refinement can happen without changing endpoint contracts.

Schedules must parse form inputs in the farm timezone, not silently in the browser's timezone. Test a browser in a different timezone and daylight-saving transitions. Reject nonexistent local times and disambiguate duplicated local times before sending offset-aware timestamps.

This version displays raw submitted data and tags but does not provide an approval queue or a general log-correction editor.

# 9. Map contract

Store actual field geometry in PostGIS. API clients exchange GeoJSON. GeoJSON positions use longitude then latitude, and polygon rings close by repeating the first position. Validate geometry before storage, normalize Polygon to MultiPolygon, and use SRID 4326. [S18][S19]

A bare-bones field editor consists of a name input and GeoJSON textarea with server validation. A draw-on-map editor can replace it later without changing the field API.

Map behavior:
1. Load every GeoJSON page for the authenticated farm.
2. Fit the viewport to the computed farm bounding box.
3. Hover a polygon to change its styling and display its name.
4. Clicking the polygon selects it, zooms with fitBounds, and opens a side panel.
5. Query `GET /logs?field_id=<id>&limit=10&direction=desc`.
6. Display the latest ten matching reports and let the user open their shared detail view.
7. Closing the panel clears selection and restores the available map width.

MapLibre renders map layers; the satellite imagery comes from the configured provider. Supply a licensed style/tile URL and required attribution. MapLibre's official example demonstrates a satellite raster layer; it does not provide a blanket license for all imagery. [S20]

Use `VITE_MAP_STYLE_URL` for provider configuration. A public map token may be embedded where the provider requires it, with origin restrictions where supported. It is not an OpenAI or database secret.

Do not plot a moving employee dot. A point used to label a field represents that field, not a worker GPS coordinate. Null-field reports display an explicit “Field not identified” state.

# 10. Backend organization

```text
farm-voice-app/
  backend/
    app/
      main.py
      config.py
      cli.py
      db/
        base.py
        session.py
      models/
      schemas/
      api/
        dependencies.py
        auth.py
        farms.py
        members.py
        fields.py
        activities.py
        fertilizers.py
        shifts.py
        recordings.py
        logs.py
        dashboard.py
        tags.py
        realtime.py
      services/
        auth_service.py
        membership_service.py
        storage_service.py
        interview_service.py
        extraction_service.py
        log_service.py
        dashboard_service.py
      prompts/
        interview_v1.py
        extraction_v1.py
    alembic/
    tests/
    pyproject.toml
    requirements.txt
    vercel.json
    .env.example
  frontend/
    src/
      api/
      components/
      features/
        auth/
        dashboard/
        logs/
        map/
        employees/
        schedule/
        settings/
        worker/
      routes/
    package.json
    package-lock.json
    vite.config.ts
    vercel.json
    .env.example
  docs/
  docker-compose.yml
  .github/workflows/ci.yml
  .gitignore
  README.md
```

Use synchronous SQLAlchemy for the ordinary CRUD services. For the bounded extraction route, use an async provider client inside an enforced wall-clock timeout, and run the short blocking database load/commit steps in a suitable threadpool. Keep SDK retries disabled there. An HTTP client's individual connect/read timeouts alone are not the overall request deadline. Never call blocking database or storage SDK operations directly on the async event loop. Normal synchronous FastAPI routes may continue to call the synchronous CRUD services.

Routers handle HTTP and dependencies. Services handle business behavior. Models handle persistence. Pydantic schemas handle input/output. Storage and AI adapters are replaceable and mockable in tests.

No user, farm, session, or submission state may live only in module memory. A module-scoped database engine or SDK client is fine; individual request sessions and tenant contexts are not shared.

# 11. Database connections and migrations

Use Supabase's transaction pooler for the Vercel API and a separate direct or suitable session connection for migration work. Current Supabase guidance distinguishes these use cases and notes prepared-statement limitations in transaction mode. [S6]

With psycopg 3 and SQLAlchemy, disable automatic prepared statements for transaction pooling with the appropriate driver setting, such as `prepare_threshold=None`. Start with a small application pool, `pool_size=1`, `max_overflow=0`, `pool_pre_ping=True`, and a bounded pool timeout. Release connections before external model/storage calls. Test under concurrent requests before increasing the pool. Psycopg and SQLAlchemy document these configuration mechanisms. [S21][S22]

Require encrypted database connections and configure certificate verification where supported. Keep the API near the database region.

Alembic creates tables, indexes, checks, and FK relationships. Enable the PostGIS extension through a migration-capable/operator connection and use the correct extension schema. Do not grant runtime DDL privileges merely to make startup succeed.

Run migrations as an explicit deployment/release step. Never run `create_all()` or migrations on every FastAPI startup or every Vercel preview build. Preview and production deployments must not race to modify the same production database.

Provide a seed command that creates fictional accounts, at least two isolated farms, several fields, activities, and fertilizers, scheduled shifts, and sample logs. Seed passwords must come from local input/config and never be published as production defaults.

Local development uses a PostGIS-enabled PostgreSQL container matching the selected managed database major version. Integration tests need actual PostGIS, not SQLite.

# 12. GitHub and Vercel deployment

## 12.1 Separate projects

Create these two Vercel projects from the same GitHub repository:
- Frontend root: `frontend/`, framework Vite, build command `npm run build`, output `dist`.
- Backend root: `backend/`, FastAPI entrypoint `app/main.py`.

The backend exports `app = FastAPI(...)`. Vercel documents this entrypoint and per-function duration configuration. [S1]

Backend `vercel.json`:

```json
{
  "functions": {
    "app/main.py": {
      "maxDuration": 60
    }
  }
}
```

Frontend routing example:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-FASTAPI-PROJECT.vercel.app/api/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

Replace the backend origin with the real stable deployment origin. The API rule must take precedence over the SPA fallback. Verify that `/api/v1/not-a-route` returns a JSON API 404 rather than the frontend HTML.

Use a Vite development proxy from `/api` to the local FastAPI server so development follows the same browser-origin pattern. Avoid maintaining separate credential flows for local and production.

Test forwarded cookies, Set-Cookie headers, Origin validation, no-store headers, and API error handling through the actual deployed rewrite. Also ensure deployment protection on the backend does not unexpectedly block legitimate proxied application calls. Do not disable application authentication to solve a routing issue.

## 12.2 Environment variables

Backend runtime:

```dotenv
APP_ENV=production
DATABASE_URL=<pooled PostgreSQL connection string>
APP_ORIGINS=["https://YOUR-FRONTEND.vercel.app"]
COOKIE_SECURE=true
CSRF_SECRET=<independent strong random server secret>
RATE_LIMIT_SECRET=<independent strong random server secret>
AWS_REGION=<bucket region>
AWS_ACCESS_KEY_ID=<least-privilege server credential>
AWS_SECRET_ACCESS_KEY=<server secret>
S3_BUCKET=<private versioned audio bucket>
OPENAI_API_KEY=<server-only project key>
OPENAI_REALTIME_MODEL=<enabled Realtime model>
OPENAI_TRANSCRIPTION_MODEL=<enabled input-transcription model>
OPENAI_EXTRACT_MODEL=<enabled model supporting Structured Outputs>
AI_REQUEST_TIMEOUT_SECONDS=45
MAX_RECORDING_BYTES=26214400
MAX_RECORDING_DURATION_MS=600000
```

Migration/CLI environment only:

```dotenv
MIGRATION_DATABASE_URL=<direct or migration-compatible connection>
```

Frontend:

```dotenv
VITE_API_BASE_URL=/api/v1
VITE_MAP_STYLE_URL=<licensed satellite style URL>
```

Keep model IDs configurable and record the actual extractor model on each log. Validate the chosen models in a deployment smoke test. Do not hardcode an unverified model identifier or silently swap to mock AI when credentials fail.

Vite's prefixed environment variables are exposed to client code, so only public configuration goes in `VITE_*` variables. Real backend secrets stay in the backend project's environment. [S23]

Commit `.env.example` with placeholders; ignore actual `.env`, `.env.*.local`, build artifacts, local audio, caches, and credentials. A local `.env` file is not a replacement for setting environment variables in each Vercel project/environment.

Preview builds use isolated test data, bucket prefixes or buckets, explicit preview origins, and an appropriate test API origin. Do not send arbitrary preview builds to production records by default.

## 12.3 One-time external setup

A generated repository cannot create provider accounts or supply your credentials by itself. The codebase must therefore be complete with placeholders and fail clearly when a required live integration is unavailable. Before a complete live deployment, configure:
- Managed PostgreSQL and enable PostGIS; create separate development and production databases where practical. Run Alembic migrations rather than manually creating tables.
- A private, versioned S3 bucket. Configure bucket CORS for the intended frontend origin. Give the backend a least-privilege IAM role/user limited to the required bucket operations (`s3:PutObject`, `s3:GetObject`, `s3:HeadObject`, plus any explicitly implemented cleanup permission). Never use `s3:*` for the application credential.
- OpenAI project key, enabled Realtime/transcription/extraction model selections, and spend limits. The permanent key is backend-only.
- Licensed satellite map configuration/style URL and any provider-side origin restrictions.
- Two Vercel projects, environment variables, and the frontend-to-backend rewrite.

The repository must include `.env.example` files with empty placeholders. Real AWS, OpenAI, database, Vercel, session, or provider credentials must never be committed or pasted into source files. After cloning, the intended production path is: provision providers, paste secrets into Vercel environment variables, run migrations/seed as appropriate, deploy, and run the smoke-test checklist.

This is a deployment checklist, not a claim that these resources already exist.

# 13. Alternatives and why this route was selected

| Alternative | Reason to choose it | Reason it is not the default here |
|---|---|---|
| FastAPI on a persistent container host, frontend on Vercel | Better fit when the design includes longer-lived processes, background workers, or heavier media processing | The current scoped API uses bounded requests and direct storage upload; two Vercel projects match the stated hosting preference |
| Next.js business API with the frontend | One JavaScript deployment and shared server/client language | Conflicts with the requested separate backend and gives up the user's FastAPI familiarity |
| Managed authentication provider | Can reduce custom identity and recovery code | Adds provider-specific integration and login/account-provisioning choices; current v1 selects provisioned usernames and a narrowly specified session system |
| Store audio in PostgreSQL | Keeps bytes and records under one persistence system | Enlarges database storage/backups and puts media delivery on the database/application path; object storage keeps the report database focused |
| A nonrelational primary database | Useful for some document-centric applications | This product relies heavily on membership, scheduling, field/activity/fertilizer relationships, filtering, and spatial records; PostgreSQL directly matches the selected data model |
| Asynchronous report generation with a queue | Handles long/retried jobs independently of the browser request | Requires durable job state and operational components explicitly excluded from this version |

There is no universal optimum. This design optimizes for the specified scope, FastAPI familiarity, relational/spatial data, and changeable frontend components. The largest tradeoffs are maintaining authentication and requiring a user retry after a synchronous extraction failure.

Keep the service interfaces clean so the backend host or extraction execution strategy can change later without redesigning the report API. Do not build those alternatives into this version preemptively.

# 14. Operational rules

Maintain structured technical logs with request ID, endpoint, elapsed time, result code, and sanitized upstream error type. Do not log passwords, session cookies, signed URLs, provider client secrets, or full transcripts by default.

Provide an operator `maintenance --dry-run` command for expired sessions/rate buckets and abandoned unconfirmed upload metadata. Never automatically delete confirmed audio merely because no log exists.

An S3 lifecycle rule must not expire a version that is still referenced by a recording, even if it became a noncurrent version after another upload. Confirmed audio retention is an explicit future/operator decision, not a hidden short TTL. Expiring a signed URL does not delete the audio.

Configure backups and test restore behavior for the chosen database/storage plans before using important data. Keep migration credentials out of frontend builds and ordinary API logs.

# 15. Acceptance tests

The implementation is not complete because the UI renders. Require automated tests plus live provider/browser smoke tests.

## Authentication and tenant isolation
- Passwords are hashed; safe API models never include password_hash or session token hashes.
- Login issues the intended cookie; logout and password change revoke sessions.
- A temporary-password account cannot use ordinary farm APIs before changing it.
- Worker requests for another worker's logs/audio/schedule cannot retrieve them.
- An admin of Farm A cannot read/change Farm B's resources by changing a UUID or farm path.
- Cross-farm fields, activities, fertilizers, recordings, shifts, and tags are rejected by services and composite FKs.
- Two concurrent admin changes cannot disable/demote every farm admin.
- A farm admin cannot reset a shared account or another admin through the worker-reset route.
- Missing CSRF, invalid Origin, and disallowed content types are rejected.
- Rate limiting works across concurrent requests using shared counters.

## Recording and AI behavior
- An identical recording initialization retry returns the same ID.
- Conflicting metadata with the same client submission ID returns 409.
- Storage upload is direct, private, constrained by size/type/key, and confirmed server-side.
- Report creation is rejected before successful upload confirmation.
- Playback always uses the pinned object version.
- Unknown field/activity/fertilizer answers produce null through the extraction contract; an unauthorized invented ID cannot be persisted.
- An AI timeout preserves the recording/transcript and permits a same-recording retry.
- Concurrent creation attempts produce at most one database log.
- A repeated successful request returns the existing report; conflicting shift input returns 409.
- The permanent provider key never appears in the frontend bundle or browser network responses.
- Missing or failed transcription does not clear the local audio draft or fabricate a transcript.

## Dashboard, queries, and maps
- Today is calculated in the farm timezone, including daylight-saving boundary days.
- Scheduled Now counts distinct enabled workers and excludes a shift at its exact end boundary.
- Schedule range queries include intervals crossing the start/end of the displayed day.
- Confidence includes all matching non-null logs, not just the visible page.
- No-data results show zero counts and null confidence.
- Search, AND filters, and repeated timestamp values work with cursor pagination.
- Tag joins do not duplicate rows or inflate counts.
- Invalid polygons, wrong coordinate order/bounds, and cross-farm field references fail appropriately.
- Every GeoJSON page is included on the farm map.
- Field click shows the correct latest ten reports; close and expand-map behavior work.
- No log-open action creates view/read/audit records.

## Browser and deployment
- iPhone Safari and Android Chrome can record, upload, play, and seek the produced format.
- Both worker and assistant speech are present in the saved conversation.
- Losing the HTTP response after commit and retrying does not duplicate the report.
- The real Vercel rewrite preserves authentication and returns API errors rather than SPA HTML.
- Refreshing a frontend route loads that route correctly.
- Local, preview, and production secrets/data are separated.
- Real provider errors remain visible; production never silently falls back to seeded or mock results.

# 16. One-shot implementation plan, phases, and deliverables

The coding agent should read this entire specification and all supplied Figma screenshots before changing code. It should then inspect the repository and implement systematically. The goal is a runnable end-to-end product, not scaffolding. Work through the phases below in order, while continuing automatically between phases unless a genuinely blocking product decision or unavailable credential requires user input.

## Phase 1 - Project foundation
- Create the `frontend/` and `backend/` applications and repository tooling.
- Configure React, TypeScript, Vite, React Router, TanStack Query, FastAPI, SQLAlchemy, psycopg, Alembic, GeoAlchemy2/PostGIS, test tooling, linting, and formatting.
- Install and apply Geist as the global UI font.
- Create `.env.example`, ignore real secrets, and establish local/preview/production configuration boundaries.
- Build the shared frontend shell and reusable design tokens from the Figma handoff before duplicating page-specific styles.

## Phase 2 - Database and migrations
- Implement all 13 application tables and constraints from `database_schema.json`, including the fertilizer catalog and `fertilizer_id` wherever activity is represented.
- Enable PostGIS through migration/setup instructions.
- Add required indexes and farm-aware composite foreign keys.
- Create repeatable Alembic migrations from an empty database.
- Create realistic development seed data: at least one farm, two admins, eight workers, five fields, eight activities, several fertilizers, planned shifts, at least twenty logs, and tags.

## Phase 3 - Authentication and farm authorization
- Implement username/password login, Argon2id password hashing, server-side sessions, HttpOnly cookies, CSRF protection, password change, logout, temporary-password flow, and the initial-farm CLI.
- Implement the farm membership dependencies and role checks.
- Add tenant-isolation tests before building privileged UI.

## Phase 4 - Core CRUD APIs
- Implement farm, member, field, activity, fertilizer, schedule, tag, bootstrap, and settings endpoints from `api_contract.json`.
- Activity and fertilizer catalogs must remain parallel: same access rules and CRUD semantics, separate tables/types/IDs.
- Generate real OpenAPI schemas and keep frontend types aligned with the API.

## Phase 5 - Shared log query and dashboard backend
- Implement log list/detail, search, AND filters, sorting, cursor pagination, dashboard metrics, and date handling in the farm timezone.
- Every place that can filter/display activity must also filter/display fertilizer.
- Add query/index tests before UI integration.

## Phase 6 - Private audio storage
- Implement recording metadata, restricted direct S3 upload authorization, upload confirmation, pinned object version, short-lived playback URLs, waveform metadata support, idempotency, and retry behavior.
- The app credential must use least-privilege bucket permissions. Do not proxy recording bytes through FastAPI.
- Provide a provider adapter or clear configuration boundary so local tests can use a fixture without pretending production S3 succeeded.

## Phase 7 - Voice and structured extraction
- Implement backend creation of short-lived Realtime credentials and browser voice integration.
- Record both worker and assistant audio where supported, preserve transcript data, and detect a supported browser recording format.
- Inject field, activity, and fertilizer catalogs into the hardcoded interview/extraction context.
- Structured extraction returns nullable `field_id`, `activity_id`, and `fertilizer_id`, summary, fixed answer document, and confidence. Validate every returned ID against the authenticated farm before persistence.
- Preserve recording/transcript and permit retry when extraction fails.

## Phase 8 - Admin frontend
- Build every supplied admin Figma screen and its loading, empty, error, and success states.
- Implement Dashboard, Activity Logs, Log Detail, Map, Employees, Schedule, Settings, farm picker, password flow, and logout.
- Add fertilizer everywhere activity is presented in UI controls, filters, forms, cards, tables, detail views, schedules, and settings, positioning it adjacent to Activity unless a supplied layout requires a nearby equivalent placement.

## Phase 9 - Worker frontend
- Build mobile-first Worker Home, recording-ready, recording-active, upload/generation, completion/error/retry, history, and detail states.
- Show the worker's own schedule and own reports only.
- Preserve local draft audio until the backend confirms the recording/upload path has succeeded.

## Phase 10 - Map
- Implement satellite MapLibre rendering, complete farm GeoJSON loading, hover state, selected-field state, fit-to-bounds, field side panel, latest ten reports, detail opening, and close/reset behavior.
- Keep employee tracking/GPS out of scope.

## Phase 11 - UI/UX polish
- Match Figma spacing, typography, hierarchy, sizes, colors, radii, shadows, and responsive states as closely as practical.
- Implement smooth hover, focus, drawer, modal, filter, skeleton, and state transitions described in the visual handoff.
- Respect `prefers-reduced-motion`; do not sacrifice responsiveness or accessibility for animation.
- Ensure worker screens work without hover and admin screens remain usable on tablet.

## Phase 12 - Verification, deployment readiness, and handoff
Before considering the implementation finished, the coding agent must run and fix failures from:
1. Backend unit/integration tests.
2. Tenant-isolation/role tests.
3. Alembic migration from an empty database.
4. Seed script.
5. Frontend TypeScript typecheck.
6. Frontend lint.
7. Frontend production build.
8. Backend startup/import check.
9. Authentication smoke test.
10. Dashboard/log/filter/pagination smoke tests.
11. GeoJSON/map data smoke test.
12. Recording upload/playback integration test when credentials are present.
13. Realtime/extraction integration smoke test when credentials are present.
14. Vercel rewrite and frontend route-refresh smoke tests in a deployed environment.

When a test/build/migration error is encountered, fix it before finishing rather than only reporting it. Report exactly which checks ran, which passed, and which live-provider checks remain unverified because credentials were unavailable.

## Required repository deliverables
The finished repository must contain:
- Complete working `frontend/` and `backend/` source.
- Real Alembic migrations and PostGIS setup instructions.
- Seed script and realistic seed data.
- Backend tests plus frontend tests where they materially protect behavior.
- `.env.example` files, with no real secrets.
- Provider adapters/configuration boundaries for S3, maps, and AI.
- Account-bootstrap and maintenance CLI commands.
- Vercel frontend/backend configuration and rewrite.
- README with exact fresh-clone local setup and exact production deployment checklist.
- Lockfiles or pinned dependencies and CI.

Do not stop at scaffolding and do not leave TODO placeholders for core requirements. Missing live credentials may block a real external call, but they must not block implementation of the integration code or the rest of the app. External-service absence should produce a clear configuration state/error, not a crash or silent fake production success.

## Locked scope: do not build
Do not spend implementation time on messaging, notifications, payroll, billing, GPS tracking, actual clock-in/out, audit/review queues, unread-log tracking, native apps, advanced analytics, report exports, email invitations, microservices, background-job infrastructure, or other features excluded by this specification.

## Responsibility boundary
Frontend owns presentation, routing, temporary interaction/recording state, animations, filters, forms, and client-side loading states. Backend owns authentication, authorization, farm isolation, business validation, database access, canonical timestamps, pagination, S3 signing/verification, AI credential minting, extraction, and persistence. Do not move security/business rules into React.

# 17. Coding-agent handoff instructions

When this specification is pasted into a coding agent together with Figma screenshots, the agent should treat this document, `database_schema.json`, `api_contract.json`, and the screenshots as the source of truth. If visual and data requirements appear to conflict, preserve security/data integrity and ask only when the decision materially changes product behavior. Do not reopen locked architecture choices merely to suggest an alternative framework.

The expected working style is:
- Read all specifications and screenshots first.
- Inspect any existing repository before writing code.
- Implement phase-by-phase without waiting for approval after each phase.
- Ask questions only for genuinely blocking ambiguity.
- Prefer complete working vertical slices over decorative mocks.
- Do not paste or request real credentials into source files. Build against environment variables and `.env.example` placeholders.
- Keep the application runnable with clear development placeholders/configuration errors when external credentials are absent.
- Run the verification checklist, fix failures, then provide a concise implementation/deployment report.

After implementation, the intended owner setup should be minimal: provision PostgreSQL/PostGIS, S3/IAM, OpenAI, and the map provider; enter the documented environment variables in the appropriate Vercel projects; run migrations and optional seed/bootstrap commands; deploy; run smoke tests. The README must make those steps copyable and explicit.

# 18. Sources and verification

Provider documentation was checked on September 17, 2026. Product limits and SDK shapes can change; the deployment smoke tests remain mandatory. The architecture and endpoint definitions above are proposed design decisions, not quotations from these sources.


**[S1] Vercel: Deploy a FastAPI app**  
`https://vercel.com/docs/frameworks/backend/fastapi`

**[S2] Vercel: Using monorepos**  
`https://vercel.com/docs/monorepos`

**[S3] Vercel: Rewrites**  
`https://vercel.com/docs/routing/rewrites`

**[S4] Vercel: Functions limits**  
`https://vercel.com/docs/functions/limitations`

**[S5] Supabase: PostGIS**  
`https://supabase.com/docs/guides/database/extensions/postgis`

**[S6] Supabase: Connecting to PostgreSQL**  
`https://supabase.com/docs/guides/database/connecting-to-postgres`

**[S7] FastAPI: Password hashing and authentication utilities**  
`https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/`

**[S8] OWASP: Session Management Cheat Sheet**  
`https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html`

**[S9] OWASP: Cross-Site Request Forgery Prevention Cheat Sheet**  
`https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html`

**[S10] OpenAI: Realtime API browser architecture**  
`https://developers.openai.com/api/docs/guides/realtime`

**[S11] AWS Boto3: Generate a presigned POST**  
`https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/generate_presigned_post.html`

**[S12] AWS S3: Versioning workflows**  
`https://docs.aws.amazon.com/AmazonS3/latest/userguide/versioning-workflows.html`

**[S13] AWS S3: Uploading with presigned URLs**  
`https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html`

**[S14] MDN: AudioContext.createMediaStreamDestination**  
`https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/createMediaStreamDestination`

**[S15] MDN: MediaRecorder.isTypeSupported**  
`https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static`

**[S16] PostgreSQL: Date/time types**  
`https://www.postgresql.org/docs/current/datatype-datetime.html`

**[S17] OpenAI: Structured model outputs**  
`https://developers.openai.com/api/docs/guides/structured-outputs`

**[S18] RFC 7946: GeoJSON**  
`https://www.rfc-editor.org/info/rfc7946/`

**[S19] PostGIS: ST_GeomFromGeoJSON**  
`https://postgis.net/docs/ST_GeomFromGeoJSON.html`

**[S20] MapLibre: Display a satellite map**  
`https://maplibre.org/maplibre-gl-js/docs/examples/display-a-satellite-map/`

**[S21] Psycopg: Prepared statements**  
`https://www.psycopg.org/psycopg3/docs/advanced/prepare.html`

**[S22] SQLAlchemy: Connection pooling**  
`https://docs.sqlalchemy.org/en/20/core/pooling.html`

**[S23] Vite: Environment variables and modes**  
`https://vite.dev/guide/env-and-mode`
