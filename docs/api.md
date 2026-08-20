# API Reference & Route Contracts

All endpoints are prefixed with `/api`.

## 1. System & Health

### `GET /api/health`
Checks API readiness and operational health.

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "discharge-orchestration-api"
}
```

---

## 2. Planned Domain Routes

### Patient & Admission Management
- `GET /api/patients`: Paginated list of patients
- `GET /api/patients/{id}`: Detailed patient record with active admission, vitals, medical history
- `POST /api/patients`: Register patient
- `GET /api/admissions/active`: List current admissions
- `POST /api/admissions`: Admit a patient and atomically claim an available ward
  bed. The operation synchronizes the bed to `occupied`, permits at most one
  active (`admitted`, `discharging`, or `transfer_pending`) admission per bed,
  and returns a controlled conflict for unavailable beds or concurrent losers.

### Bed Management and Manual Release

Feature 4 exposes a controlled, staff-operated bed-turnover workflow. Clinical
approval of a discharge report does **not** automatically release a bed, discharge
the admission, or contact n8n. A doctor or ward administrator must explicitly
perform each permitted action.

#### `GET /api/beds`

Returns operational bed summaries. Optional exact-match query filters are:

- `status`: `available`, `occupied`, `vacating`, `cleaning`, or `reserved`.
- `ward`: ward name.
- `skip` and `limit`: pagination controls (`limit` is 1–100 and defaults to 100).

Each summary includes the bed identity and status, current patient name/code and
ID when assigned, matching admission ID/status, primary diagnosis,
`release_eligible`, and `updated_at`. Search by bed number, patient name, or
patient code is intentionally a client-side filter over this operational set.

#### `GET /api/beds/{bed_id}`

Returns the same operational summary plus `transition_history`, ordered newest
first. Each history item contains the event type, previous/new bed status, and
creation time. Current patient information is provided only while a bed is
`occupied` or `vacating`. For `cleaning` and `available` beds, the most recent
discharged admission remains available as historical context but is not current
ownership. Sensitive demographics and clinical notes are excluded.

#### `POST /api/beds/{bed_id}/start-release`

Starts release only when an `occupied` bed has a current patient, a matching
`discharging` admission, an approved discharge report, and its internal
`report_approved` event. It changes the bed from `occupied` to `vacating` and
creates one pending `bed_release_started` audit event. The patient assignment
remains in place and the admission remains `discharging`.

The operation is idempotent for the same consistent `vacating` bed, admission,
and report: it returns the current detail without creating another event.

#### `POST /api/beds/{bed_id}/patient-departed`

Confirms physical departure for a consistent `vacating` bed. In one transaction
it changes the bed to `cleaning`, clears `current_patient_id`, and changes the
matching admission from `discharging` to `discharged` while preserving its
`bed_id` and history. It creates pending `patient_departed_bed` and
`bed_cleaning_started` audit events. Repeats and stale requests are conflicts.

#### `POST /api/beds/{bed_id}/cleaning-complete`

Completes turnover only for a `cleaning` bed without a current patient. It changes
the bed to `available`, keeps the assignment empty, and creates one pending
`bed_available` audit event. Repeats and stale requests are conflicts.

#### State, authorization, and errors

The only normal Feature 4 path is:

```text
occupied -> vacating -> cleaning -> available
```

`reserved` remains supported but has no Feature 4 transition. Direct or skipped
transitions are rejected. The three action routes require the server-derived
development user to have the `doctor` or `ward_admin` role; callers cannot select
the actor in the request payload. An absent development user returns `401`; an
unauthorized role returns `403`; a missing bed returns `404`; invalid, stale, or
inconsistent release state (including a missing required admission/report context)
returns a controlled `409`. Existing request-validation errors use the standard
`422` response contract.

Bed transition events use `WorkflowEvent` with `entity_type: "bed"` and the bed
ID. Their payload records the bed, patient, admission, prior/new state, UTC
timestamp, and actor; the start event also records the discharge report ID. All
Feature 4 events are internal and `pending`: no n8n publication, cleaning
automation, transfer departure, notification, or other external workflow occurs.

### Discharge Orchestration
- `GET /api/discharge/admissions/{admission_id}/report`: Fetch the report for an admission
- `POST /api/discharge/generate/{admission_id}`: Explicitly request an AI draft (`status: generated`)
- `PUT /api/discharge/reports/{report_id}/edit`: Doctor edits the draft (`status: under_review`)
- `POST /api/discharge/reports/{report_id}/approve`: **Doctor explicit approval** (`status: approved` and one internal `report_approved` audit event)

Draft generation requires `REPLICATE_API_TOKEN`. The default model is configured with
`LLM_MODEL=openai/gpt-5.6-luna`; reasoning effort, verbosity, and maximum completion tokens
are also configurable in `backend/.env`. Provider output is always persisted as an
unapproved draft. Approval does not discharge the patient, release a bed, or publish an
external workflow.

### Inter-Hospital Transfers
- `GET /api/transfers`: Active transfers across network
- `POST /api/transfers`: Initiate transfer request (`status: matching`)
- `PATCH /api/transfers/{id}/accept`: Receiving hospital acceptance
- `GET /api/hospitals`: Network hospitals and live capacity

### Ambulance Dispatch
- `GET /api/ambulances/dispatches`: Active dispatches
- `POST /api/ambulances/dispatch`: Request transfer vehicle
- `PATCH /api/ambulances/dispatches/{id}/status`: Transition dispatch status (`requested` ➔ `en_route` ➔ `arrived` ➔ `patient_onboard` ➔ `completed`)

### Workflow Events

Workflow events are persisted internal audit records. The current API neither
publishes them to n8n nor provides a webhook retry endpoint.

- `GET /api/events`: Lists events newest first. Optional exact filters are
  `event_type` and `status`; `skip` defaults to 0 and `limit` defaults to 50.
  Server-derived authentication is required and access is limited to doctors and
  ward administrators. Responses contain only operational metadata (`id`, event
  and entity identifiers, status, and creation time); arbitrary payload, actor,
  and patient details are not exposed.

There is no external event-creation endpoint. Domain services are the only
workflow-event writers.
