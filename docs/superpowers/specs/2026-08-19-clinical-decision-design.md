# Feature 2: Doctor Decision and Discharge/Transfer Entry Flow

## Purpose

Add the human-controlled clinical branching point that records whether the doctor intends to discharge or transfer an admitted patient. The feature persists a draft, requires explicit review and confirmation, changes the admission into the correct preparation state, and creates an internal audit event. It does not execute discharge or transfer operations.

## Scope

Feature 2 includes:

- A persisted clinical decision associated with a patient, active admission, and doctor.
- Draft creation and editing with controlled validation.
- Explicit confirmation that transitions the admission to `discharging` or `transfer_pending`.
- Duplicate-active-decision protection.
- Internal `WorkflowEvent` audit records created atomically on confirmation.
- A two-step React decision and review flow with a confirmation dialog.
- Existing-decision display and state-aware actions on the patient profile.
- Backend tests, migration verification, frontend typechecking, and production build verification.

Feature 2 excludes LLM report generation, report signing, PDFs, hospital matching, receiving-hospital approval, bed release, ambulance dispatch, maps, n8n calls, webhooks, messaging, real authentication, and real EHR integration.

## Existing-System Integration

The implementation extends the existing FastAPI route/service/repository pattern, SQLAlchemy `Patient`, `Admission`, `User`, and `WorkflowEvent` models, development-user dependency, Alembic revision chain, React Router setup, patient detail endpoint, shared Axios client, status badge, and current discharge/transfer placeholders. No duplicate API client, routing system, admission model, event table, or transfer workflow will be created.

## Domain Model

Add `ClinicalDecision` with:

- `id`: integer primary key.
- `patient_id`: required restrictive foreign key to `patients.id`.
- `admission_id`: required restrictive foreign key to `admissions.id`.
- `decision_type`: controlled `discharge` or `transfer` value.
- `transfer_urgency`: nullable controlled `emergency` or `non_emergency` value.
- `reason`: required text after trimming.
- `required_specialty`: nullable bounded string selected from the supported list by the frontend and validated as non-empty for transfers by the backend.
- `notes`: optional text.
- `decided_by`: required restrictive foreign key to `users.id`.
- `decided_at`: nullable timestamp set only on confirmation.
- `status`: controlled `draft`, `confirmed`, or `cancelled` value.
- `created_at` and `updated_at`: timezone-aware timestamps.

Relationships:

- A patient has clinical decisions.
- An admission has clinical decisions.
- A user has decisions they made.
- A clinical decision belongs to exactly one patient, admission, and deciding user.

The service derives `patient_id` from the admission and `decided_by` from the existing development-user dependency. Clients cannot choose either identity in the request body.

## Decision Invariants

- Only an `admitted` admission can receive a new decision.
- An admission may have at most one non-cancelled decision (`draft` or `confirmed`). The service checks this rule and the database enforces it with a partial unique index on PostgreSQL where supported by the migration.
- A draft may be edited while its admission remains `admitted`.
- A confirmed or cancelled decision cannot be edited or reconfirmed.
- A decision's admission and patient relationship cannot change.
- Confirmation is one explicit doctor action and cannot be inferred or triggered by AI.

Discharge validation:

- `reason` is required.
- `transfer_urgency` and `required_specialty` must be absent. Inappropriate supplied values produce HTTP 422 rather than being silently discarded.

Transfer validation:

- `reason`, `transfer_urgency`, and `required_specialty` are required.
- `required_specialty` is trimmed and must not be empty.

Notes are optional for either decision type.

## State Transitions

Creating or updating a draft does not change the admission.

Confirmation runs in one database transaction:

### Discharge

```text
clinical decision: draft -> confirmed
admission: admitted -> discharging
bed: unchanged
event: clinical_discharge_decision_confirmed
```

### Transfer

```text
clinical decision: draft -> confirmed
admission: admitted -> transfer_pending
bed: unchanged
event: clinical_transfer_decision_confirmed
```

The event uses `entity_type="clinical_decision"`, `entity_id=<decision id>`, `status="pending"`, and a payload containing `patient_id`, `admission_id`, `decision_id`, `decision_type`, nullable `transfer_urgency`, and nullable `required_specialty`. The event is stored for audit and future orchestration; Feature 2 does not dispatch it externally.

## Backend Layers

### Repository

`ClinicalDecisionRepository` owns database reads and persistence:

- `get(decision_id)` with admission/patient/doctor eager loading.
- `get_active_for_admission(admission_id)` returning the newest non-cancelled decision.
- `add(decision)` without independently committing.

### Service

`ClinicalDecisionService` owns business rules:

- Load and validate admissions.
- Reject new decisions on unknown or non-admitted admissions.
- Reject duplicate non-cancelled decisions.
- Create a validated draft with the authenticated development doctor.
- Return the current active decision or HTTP 404.
- Update draft-only editable fields.
- Confirm the draft, transition the admission, and insert the audit event in one transaction.
- Roll back and return controlled errors without database details.

### Routes

Routes validate request shapes and delegate to the service. The existing `get_current_user_stub` supplies the deciding doctor; if no development user exists, the route returns HTTP 401. Feature 2 does not add authentication.

## API Contract

### `POST /api/admissions/{admission_id}/clinical-decision`

Creates a draft. Request fields:

- `decision_type`
- nullable `transfer_urgency`
- `reason`
- nullable `required_specialty`
- nullable `notes`

Returns HTTP 201 with the typed decision. Unknown admission returns 404. Non-admitted admission or duplicate active decision returns 409. Invalid field combinations return 422.

### `GET /api/admissions/{admission_id}/clinical-decision`

Returns the newest non-cancelled decision for the admission. Unknown admission or no current decision returns 404 with a safe message.

### `PUT /api/clinical-decisions/{decision_id}`

Replaces editable draft decision fields using the same validation contract as creation. Unknown decision returns 404. A non-draft decision returns 409.

### `POST /api/clinical-decisions/{decision_id}/confirm`

Explicitly confirms a draft and returns the confirmed decision. Confirmation updates admission state and writes the audit event atomically. Unknown decision returns 404; non-draft or invalid admission state returns 409.

## Migration

Create an Alembic revision after `20260819_0001` that creates the `clinical_decisions` table, controlled enum-compatible columns, indexes, foreign keys, and PostgreSQL partial unique index preventing more than one `draft` or `confirmed` decision per admission. The downgrade removes only Feature 2 structures. Existing patient data and the baseline schema remain untouched.

## Frontend Types and API

Add shared TypeScript types:

- `ClinicalDecisionType`
- `TransferUrgency`
- `ClinicalDecisionStatus`
- `ClinicalDecision`
- `CreateClinicalDecisionRequest`

Add `api/clinicalDecisions.ts` using the shared Axios client:

- `createClinicalDecision(admissionId, request)`
- `getClinicalDecision(admissionId)`
- `updateClinicalDecision(decisionId, request)`
- `confirmClinicalDecision(decisionId)`

The supported specialties live in one frontend constant exported by the decision module: Cardiology, Neurology, Orthopedics, General Surgery, Critical Care, Pulmonology, Nephrology, and Gastroenterology.

## Clinical Decision Page

Add `/patients/:patientId/decision` and a focused `ClinicalDecisionPage`.

The page loads the existing patient detail first. It requires a current admission and displays a compact summary: patient name/code, age, gender, diagnosis, ward/bed, and admission status. It then requests the current decision for that admission. A 404 means no decision and is treated as the blank-flow state; other errors show a safe error and Retry.

### Step 1: Decision

Two large accessible single-select cards choose `Discharge Patient` or `Transfer Patient`. Selection is represented by radio semantics, visible labels, and an explicit selected indicator rather than color alone.

Discharge fields:

- Required reason.
- Optional clinical notes.

Transfer fields:

- Required urgency selection.
- Required specialty select.
- Required reason.
- Optional clinical notes.

Emergency shows: `Emergency transfers will follow an expedited workflow after the clinical decision is confirmed.`

Non-emergency shows: `The receiving facility will require confirmation before transport begins.`

`Review Decision` validates locally for immediate usability, then advances without calling confirmation.

### Step 2: Review

The review shows patient, decision type, transfer urgency/specialty when applicable, reason, and notes. `Back to Edit` returns to the form. `Confirm Decision` first saves a new draft or updates the existing draft, then opens a lightweight confirmation dialog. The dialog explains the exact admission consequence and offers Cancel and Confirm.

Confirm calls the confirmation endpoint once. While pending, controls are disabled. Success renders a restrained success message and navigates:

- Discharge: `/patients/{patientId}/discharge`.
- Transfer: `/transfers/new?patientId={patientId}`.

No generated report, matching, ambulance, or emergency operation is claimed.

### Existing decision

If a draft exists, populate the form so the doctor can continue editing and reviewing it.

If a confirmed decision exists, show `Current Clinical Decision` with decision, urgency, specialty, reason, notes, deciding doctor, decision time, and status. Do not show a blank form. Offer:

- `Continue to Discharge Report` for discharge.
- `Continue to Transfer Workflow` for transfer.

## Patient Profile Integration

Update the primary action based on admission state:

- `admitted`: `Start Discharge / Transfer` -> decision page.
- `discharging`: `Continue Discharge` -> discharge placeholder.
- `transfer_pending`: `Continue Transfer` -> `/transfers/new?patientId=...`.
- Other states: no start action.

The profile continues to render the admission status supplied by the Feature 1 API.

## Error Handling

- Backend Pydantic validation produces the existing safe HTTP 422 envelope.
- Business conflicts return HTTP 409 with human-readable messages.
- Missing admissions/decisions return HTTP 404.
- Database errors are logged, rolled back, and returned as generic HTTP 500 messages.
- Frontend never renders raw Axios errors and provides Retry where loading can fail.
- Double confirmation clicks are prevented in the UI and rejected by the backend.

## Testing and Verification

Backend tests cover:

- Create a discharge draft.
- Create non-emergency and emergency transfer drafts.
- Reject transfer without specialty or urgency.
- Reject inappropriate transfer fields on discharge.
- Reject unknown admission.
- Get an existing decision and return 404 when absent.
- Update a draft and reject updating a confirmed decision.
- Confirm discharge and transition `admitted -> discharging` without changing the bed.
- Confirm transfer and transition `admitted -> transfer_pending` without changing the bed.
- Reject duplicate active decisions.
- Create the correct internal audit event and payload.
- Preserve atomicity when confirmation fails.

Verification requires:

- Full pytest suite passes.
- Migration upgrade/downgrade/upgrade succeeds on an isolated database; PostgreSQL is used if available and an infrastructure limitation is reported otherwise.
- Frontend TypeScript check passes.
- Vite production build passes.
- Manual/live API flow verifies draft, review-equivalent confirmation, status transitions, current-decision retrieval, and audit events.

## Next Feature Boundary

Stop after Feature 2. Feature 3 is AI-Assisted Discharge Report Generation plus Doctor Review and is not part of this implementation.
