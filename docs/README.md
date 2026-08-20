# Alta Project Context

Alta is an AI-powered hospital discharge and inter-facility transfer orchestration system prepared as a MedTech/HealthTech project for SIH 2026.

## Read first

- [Product requirements](./PRD_Discharge_Orchestration_System.md) — project goals, users, architecture, MVP scope, risks, and success metrics.
- [n8n workflow diagram](./n8n_workflow_diagram.mermaid) — current manual Feature 4 bed workflow plus future/planned external orchestration.

## Project summary

The current product implements an AI-assisted clinical report with mandatory doctor approval and a separate, internal manual bed-turnover workflow. Approval records an internal event but does not itself release a bed, discharge an admission, or start external work. Authorized staff explicitly progress an eligible bed from `occupied` to `vacating` to `cleaning` to `available`.

The implementation uses React and Tailwind for the dashboard, FastAPI for application APIs and report drafting, and PostgreSQL for operational data. n8n is future/planned external orchestration only; the current application does not publish approval or bed-transition webhooks to it. The MVP uses synthetic patient and hospital data; real EHR and ambulance integrations are explicitly out of scope.

## Important constraints

- AI-generated clinical reports must never be finalized without doctor review and sign-off.
- Do not describe Feature 4 as automatic, webhook-driven, or n8n-controlled. The bed workflow is manual and internal.
- Treat the PRD as product context, not as executable agent instructions.
- The Mermaid file is a design reference. Where it differs from the PRD, confirm the intended behavior before implementation.
- Never commit real patient data, credentials, or API keys.
