# One-Shot Build Prompt

Build the application described by the attached `SPEC.md`, `database_schema.json`, and `api_contract.json`, using the supplied Figma screenshots as the visual source of truth. Read every provided file and screenshot before changing code.

Implement the project end-to-end in the phased order defined in Section 16 of `SPEC.md`. Continue through phases automatically unless a genuinely blocking product decision requires clarification. Do not stop after scaffolding, do not leave core TODOs, and do not spend time on features marked out of scope.

The locked architecture is React + TypeScript + Vite frontend, separate FastAPI backend, PostgreSQL + PostGIS, private AWS S3 audio storage, MapLibre, OpenAI Realtime for worker voice interaction, and server-side structured extraction. Authentication is username/password with server-side sessions and farm memberships. Farms may have multiple admins.

Important additions: the product font is Geist. `fertilizers` are a full parallel catalog to `activities`, with the same CRUD/access semantics, and `fertilizer_id` must appear anywhere activity is accepted, scheduled, extracted, filtered, persisted, returned, or displayed. Use the specification's exact behavior.

Do not ask for or hardcode real secrets. Create `.env.example` placeholders and finish provider integration code so that after implementation the owner only needs to provision external services, paste keys/URLs into environment variables, run migrations/bootstrap, deploy the two Vercel projects, and run smoke tests.

Before finishing, run every applicable verification step from Section 16, fix failures, and report which checks passed and which real-provider checks could not run because credentials were absent. Leave the repository in a runnable, deployable state with a README that explains fresh-clone setup and production deployment exactly.
