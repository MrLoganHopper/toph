# Implementation notes

## Restored handoff

Only 15 implementation files from the earlier response were present in the mounted project. The complete directory tree referred to in that response was not retained. This continuation preserved the supplied dashboard/detail/map/voice components, stylesheet, database table definitions, frozen migration, CLI, and orchestration code, and restored their missing dependencies and route modules. The current ZIP includes the whole repository rather than selected individual files.

## Source hierarchy

`SPEC.md`, `database_schema.json`, `api_contract.json`, and the original screenshots are retained as inputs. User-supplied frontend interaction notes refine the welcome-map animation, selected-field report placement, date presets, and voice confirmation behavior. `docs/openapi.json` is generated from the actual FastAPI application, not a renamed copy of the endpoint inventory.

Fertilizer is a separate farm catalog with parallel activity CRUD, access checks, protected references, nullable scheduling/report associations, filters, spoken prompts, and displayed values. It is not a task-completion status or a new workflow engine.

The repeated “fertilizer” words in some original JSON inventory descriptions are editorial duplication, not requests for repeated database columns. The original files are preserved; executable schemas have one `fertilizer_id` for each relevant relationship.

## Visual tokens and routes

Geist is the root font via a package import. Desktop sidebar width is 272px, with a 10px outer inset. At the supplied 1628px desktop viewport the main content starts near x=320. Dashboard title text is 20px, ordinary body text 14-16px, metric values approximately 48px, metric cards 112px high, rows approximately 56px, controls approximately 33px, and table radius 20px. Log cards and map frames reuse consistent radii and border treatments.

The welcome loading slit takes at least 900ms, with left-to-right reveal. Vertical opening and overlay entrance use the shared CSS easing system. Data loading runs independently. Reduced-motion preferences bypass extended visual motion. Loading, empty, configuration-error, and recoverable-error states are visible instead of simulated data.

The mobile reference width is 393px. The voice screen uses a 190px ring with a 30px stroke, large question typography, prominent live transcript, recording disclosure, and five-step counter. Active audio amplitude changes the ring scale and stroke. Review and retry content can extend below the first viewport to preserve usability.

Dashboard screenshot wording is adapted to specification-defined metrics. Out-of-scope navigation is hidden. Farm initials replace a fixed example person's photograph. Actual dataset size controls row/card count. These differences are deliberate; pixel-perfect comparison was not executed in the delivery runtime.

## Provider integration

The OpenAI adapter uses bounded raw HTTP requests through httpx. It calls the official Realtime client-secret endpoint and Responses endpoint with a strict Pydantic-derived JSON schema. There is no production mock fallback or permanently exposed provider key. A short-lived Realtime secret is returned to the browser for its direct WebRTC connection.

The AWS IAM policy corrects the original documentation's `s3:HeadObject` action name to `s3:GetObject`, and includes `s3:GetObjectVersion` for finalized playback. The storage adapter pins the version returned by a verified HEAD response. Its fixture-audio error is intentionally explicit.

The worker review permits a labelled, worker-entered transcript correction when ASR is missing/incomplete. It does not use AI-generated replacement text to pretend transcription succeeded. Captured audio remains self-reported and is not cryptographically verified against the transcript.

## Testing boundaries

Backend unit/HTTP/provider-boundary tests can run without a database. The PostGIS integration module is deliberately separate and refuses to reset a database unless its name ends in `_test` and `TOPH_TEST_RESET=YES` is present. Its provider stand-ins exist only in tests. Real S3/OpenAI calls and physical mobile media behavior remain live smoke tests.

No authentication, farm, submission, or background job state is kept only in module memory. Cached engines, SDK clients, and immutable configuration are process-level implementation objects; business state resides in the database or explicitly scoped browser drafts.

This version does not include native offline/background recording, approval/review queues, actual clock-in/out, messaging, payroll, billing, live worker location, exports, or an advanced field drawing tool.
