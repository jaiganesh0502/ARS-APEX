# Feature 3 — AI-Assisted Discharge Report Generation and Doctor Review

## Objective

Implement the discharge-report stage that follows a confirmed discharge clinical decision. The system will assemble persisted clinical context, request a draft from Replicate's `openai/gpt-5.6-luna` model, store the result as an unapproved report, allow a doctor to edit it, and require an explicit approval action before recording a `report_approved` internal event.

This feature does not release beds, call n8n, dispatch notifications, create PDFs, or finalize the patient's discharge.

## Existing Context

Feature 2 already guarantees this entry condition:

```text
confirmed discharge decision
        ↓
admission.status = discharging
        ↓
Feature 3 discharge report workflow
```

The repository already includes a `DischargeReport` model, repository, service scaffold, route scaffold, LLM interface, and frontend discharge route. Feature 3 will adapt these components rather than creating parallel report or routing systems.

## Scope

Feature 3 includes:

- clinical-context assembly from PostgreSQL;
- Replicate provider integration through the existing LLM abstraction;
- AI draft generation and persistence;
- retrieval of the current report for an admission;
- doctor editing and review-state transition;
- explicit approval with doctor and timestamp audit fields;
- internal `report_approved` event creation;
- a clinical report-generation, editing, review, and approved-state UI;
- deterministic fake-provider tests and one opt-in live-provider verification.

Feature 3 excludes:

- admission transition to `discharged`;
- bed release or cleaning;
- n8n or webhook calls;
- hospital matching or receiving-facility approval;
- ambulance, maps, email, or SMS integrations;
- PDF generation;
- real authentication or EHR integration.

## Provider Configuration

The production development provider is Replicate using:

```text
openai/gpt-5.6-luna
```

Configuration is read through application settings:

```text
REPLICATE_API_TOKEN
LLM_MODEL=openai/gpt-5.6-luna
LLM_REASONING_EFFORT=low
LLM_VERBOSITY=medium
LLM_MAX_COMPLETION_TOKENS=3000
```

The token is stored only in the ignored `backend/.env` file. It is never committed, logged, returned by an API, placed in frontend code, or included in error details.

The backend uses Replicate's Python client. `ReplicateLLMClient` implements the existing `LLMClientInterface`. Routes and services depend on the interface, not the vendor SDK.

Tests inject a deterministic fake LLM client. Provider failure never silently substitutes template content because that could misrepresent the provenance of a clinical draft.

## Clinical Context

The generation service loads the admission with its patient and available clinical relationships. It supplies only persisted fields:

- patient code and demographics;
- admission date and primary diagnosis;
- attending doctor;
- current ward and bed;
- medical-record diagnosis, treatment course, and notes;
- active and historical medications associated with the admission;
- recent vitals associated with the admission;
- confirmed discharge decision reason and notes.

Missing data is represented as unavailable; it is never invented or replaced with plausible values.

## Prompt Safety Contract

The system prompt instructs the model to:

- produce a clinical draft, not a final medical record;
- use only the provided structured context;
- never infer or fabricate diagnoses, dates, medications, test results, follow-up appointments, or instructions;
- state `Not documented` where required information is absent;
- preserve uncertainty and conflicting source information;
- avoid declaring that discharge, bed release, or downstream orchestration occurred;
- include a prominent `DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF` heading;
- return plain text with defined sections.

Required draft sections:

```text
Patient and Admission
Primary Diagnosis
Relevant Clinical History
Hospital Course and Treatment
Medication Summary
Recent Clinical Status
Discharge Decision Rationale
Recommended Follow-up for Physician Review
Outstanding Items and Missing Information
```

The model output is treated as untrusted draft text. It is length-checked, must not be blank, and is stored without rendering it as HTML.

## Domain Rules

Generation is permitted only when all conditions are true:

- the admission exists;
- admission status is `discharging`;
- an active confirmed clinical decision exists for that admission;
- the confirmed decision type is `discharge`;
- no active discharge report already exists for that admission.

Generation never approves a report. A generated report has:

```text
status = generated
approved_by = null
approved_at = null
```

Editing is allowed only for `generated` or `under_review` reports. Saving doctor edits sets:

```text
status = under_review
edited_content = doctor-controlled text
```

Approval is allowed only for `generated` or `under_review` reports, by a doctor user, and only while the admission remains `discharging`. Approval sets:

```text
status = approved
approved_by = doctor.id
approved_at = current UTC time
```

Approved reports are immutable. Repeated approval returns a conflict response.

## Persistence

The existing `discharge_reports` table remains the primary report record. A migration will add or adjust only constraints needed for Feature 3:

- one active report per admission;
- appropriate foreign-key delete behavior;
- indexes needed for admission/status lookups;
- provider provenance fields if absent:
  - `generation_provider`;
  - `generation_model`.

Generated and edited content remain separate to preserve the original AI output and the doctor-authored revision. The effective content is `edited_content` when present, otherwise `generated_content`.

Existing patient and Feature 2 data must not be reset.

## Internal Event

Approval creates one `WorkflowEvent` in the same transaction as the report approval:

```text
event_type = report_approved
entity_type = discharge_report
entity_id = report.id
status = pending
```

Payload:

```json
{
  "report_id": 1,
  "patient_id": 1,
  "admission_id": 1,
  "approved_by": 1,
  "approved_at": "UTC timestamp"
}
```

The event is internal preparation only. No event publisher may call n8n or an external webhook in Feature 3.

## Backend Architecture

```text
FastAPI route
    ↓
DischargeService
    ├── clinical-context assembler
    ├── LLMClientInterface
    ├── DischargeRepository
    └── WorkflowEvent persistence
```

The route resolves dependencies and translates known provider failures into safe HTTP responses. Clinical eligibility, transitions, duplicate prevention, and approval rules remain in the service.

The Replicate client owns provider-specific input construction and output collection. It does not query the database or approve reports.

## API

Feature 3 exposes:

```text
POST /api/discharge/generate/{admission_id}
GET  /api/discharge/admissions/{admission_id}/report
GET  /api/discharge/reports/{report_id}
PUT  /api/discharge/reports/{report_id}/edit
POST /api/discharge/reports/{report_id}/approve
```

Generate returns `201` only after provider output is successfully persisted. It returns:

- `404` for an unknown admission;
- `409` for an ineligible admission, wrong decision type, or duplicate report;
- `502` for a provider rejection/failure;
- `503` when provider credentials are unavailable;
- `504` for a provider timeout.

Provider error responses use safe generic messages and never expose credentials, raw request headers, or full clinical prompts.

The approval request does not accept an arbitrary doctor identifier from the browser. Until authentication exists, the existing development-user dependency supplies the synthetic doctor identity.

## Frontend Experience

Route:

```text
/patients/:patientId/discharge
```

The page loads the patient and current report for the active admission.

### No report

Show:

- compact patient/admission summary;
- clinical safety notice;
- explanation of the information sent for drafting;
- `Generate AI Draft` button.

The UI never generates automatically on page load.

### Generating

Show a restrained progress state. Prevent repeated submissions. Do not show fabricated partial content or an emergency-style countdown.

### Generated

Show the original AI draft as plain text with a persistent unapproved-draft warning. Actions:

- `Edit Draft`;
- `Review for Approval`.

### Editing

Use a large plain-text editor initialized from effective content. Actions:

- `Cancel`;
- `Save Changes`.

Saving transitions the report to `under_review`.

### Approval review

Show effective report content read-only, the patient identity, report status, generation model, and consequences. The doctor must check an acknowledgement confirming they reviewed the full report before `Approve Report` becomes available.

A final modal states that approval records the report as physician-approved and creates the internal downstream event, but does not discharge the patient or release the bed.

### Approved

Show a read-only report with:

- approved status;
- approving doctor;
- approval time;
- effective content;
- explicit note that final discharge and bed release are separate later steps.

## Error Handling

- Validation failures remain visible near the relevant action.
- Provider failures preserve the no-report state and allow an explicit retry.
- Saving or approval failures preserve the doctor's current editor/review content.
- Expected missing-report responses do not create browser-console errors.
- Network failures never transition the UI to generated or approved.

## Testing

Backend tests cover:

- context contains persisted clinical data and explicit missing markers;
- generation requires a confirmed discharge decision;
- transfer decisions cannot generate discharge reports;
- generation requires `discharging` admission status;
- missing provider token is rejected safely;
- fake-provider output persists as `generated` and remains unapproved;
- blank provider output is rejected;
- duplicate generation is rejected;
- report retrieval by admission;
- editing transitions to `under_review` and preserves generated content;
- approved reports cannot be edited;
- only doctor users can approve;
- approval records doctor/time;
- approval and `report_approved` event are atomic;
- repeated approval is rejected;
- approval does not change admission to `discharged` or modify the bed.

Frontend tests cover:

- no automatic generation;
- generation loading and failure states;
- generated draft warning;
- edit/save behavior;
- approval acknowledgement and modal;
- approved read-only state;
- downstream actions are not claimed.

Verification commands:

```text
backend/.venv/Scripts/python.exe -m pytest -q
npm test
npm run lint
npm run build
```

PostgreSQL verification applies the migration without resetting data and checks constraints, report transitions, audit fields, and workflow events.

One opt-in live-provider test uses a synthetic patient and the configured Replicate token. Automated tests never consume paid provider calls.

## Completion Criteria

Feature 3 is complete only when:

```text
confirmed discharge decision
        ↓
doctor explicitly starts generation
        ↓
Replicate produces an unapproved draft
        ↓
draft persists in PostgreSQL
        ↓
doctor reviews and optionally edits
        ↓
doctor explicitly approves
        ↓
approval audit fields and internal event persist atomically
```

At completion, the admission remains `discharging`, the bed remains occupied, and no external orchestration has been invoked.

## Next Feature

Do not implement as part of Feature 3:

```text
Feature 4 — Post-Approval Discharge Finalization and Bed-Release Workflow
```
