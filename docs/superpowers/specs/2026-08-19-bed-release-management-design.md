# Feature 4 — Bed Release and Bed Management Design

## Purpose

Convert an approved discharge report into a controlled, auditable bed-turnover workflow without making the bed immediately available.

## Scope

Feature 4 implements manual bed release for ordinary discharge cases, operational bed list/detail APIs, a real Bed Management UI, and small patient/discharge/dashboard integrations. Transfer departure, n8n execution, hospital matching, ambulance dispatch, notifications, reservations, and cleaning automation remain out of scope.

## State Machine

The only normal turnover path is:

```text
occupied → vacating → cleaning → available
```

- `reserved` remains structurally supported but has no Feature 4 transition.
- Direct `occupied → available`, `occupied → cleaning`, `vacating → available`, and `cleaning → occupied` transitions are forbidden.
- Existing unrestricted status mutation must be removed or constrained so it cannot bypass the service.

## Domain Semantics

- Report approval is clinical approval only. It does not move the bed.
- Starting release means operational preparation: bed `occupied → vacating`; admission remains `discharging`; patient assignment remains present.
- Confirming departure means the patient physically left: bed `vacating → cleaning`; `current_patient_id` becomes null; admission `discharging → discharged`; admission history and `bed_id` remain preserved.
- Completing cleaning means the bed is ready: bed `cleaning → available`; patient assignment must remain null.
- An occupied bed must have a current patient and a matching active admission. An available bed must not have a current patient or active admission ownership.

## Architecture

Create a dedicated `BedReleaseService`. Routes perform request parsing, authentication, and error translation only. The service owns eligibility, locking, conditional transitions, related-record updates, idempotency, and audit-event creation.

Each transition uses a database transaction. PostgreSQL row locking and a conditional status update protect against concurrent staff actions. The conditional update is also authoritative on databases where row locks are weaker. A stale transition returns a controlled conflict and cannot partially update related records.

Manual Option A is used: the dashboard detects eligibility and staff explicitly starts release. No automatic event handler or n8n call is introduced.

## Authorization

Use the existing server-derived development user dependency. Doctors and ward administrators may perform turnover actions. Client payloads cannot select the actor. Authorization is enforced in both route and service layers.

## Start Release

`POST /api/beds/{bed_id}/start-release`

Required current state:

- bed exists and is `occupied`;
- bed has `current_patient_id`;
- matching admission exists, references this bed and patient, and is `discharging`;
- matching discharge report is `approved`;
- a `report_approved` workflow event exists for that report.

The transaction changes the bed to `vacating` and adds one `bed_release_started` event. It does not clear the patient or discharge the admission.

Repeating the same operation while that bed/admission is already `vacating` returns the current state without another event. A vacating bed with inconsistent ownership is not treated as idempotent and returns conflict.

## Confirm Patient Departure

`POST /api/beds/{bed_id}/patient-departed`

Required current state is a consistent `vacating` bed and matching `discharging` admission. One transaction:

- changes bed to `cleaning`;
- clears `current_patient_id`;
- changes admission to `discharged`;
- preserves admission `bed_id` and all history;
- creates `patient_departed_bed` and `bed_cleaning_started` events.

Repeated or stale departure requests return conflict rather than duplicating events.

## Complete Cleaning

`POST /api/beds/{bed_id}/cleaning-complete`

Required current state is `cleaning` with no current patient. One transaction changes the bed to `available` and creates one `bed_available` event. Assignment must remain null. Repeated or stale requests return conflict.

## Audit Events

Reuse `WorkflowEvent` with `entity_type = "bed"` and `entity_id = bed.id`.

Event types:

- `bed_release_started`
- `patient_departed_bed`
- `bed_cleaning_started`
- `bed_available`

Payloads contain `bed_id`, `patient_id`, `admission_id`, `previous_status`, `new_status`, UTC timestamp, actor user ID/name/role, and related report ID where applicable. All events are internal and `pending`; Feature 4 does not publish them externally.

## Read APIs

`GET /api/beds`

- Supports exact `status` and `ward` filters.
- Returns operational summaries containing bed identity, status, current patient name/code when assigned, admission ID, diagnosis, eligibility to start release, and last update.
- Search stays a frontend filter over the returned operational set for this MVP.

`GET /api/beds/{bed_id}`

- Returns the summary fields plus admission status and ordered bed-transition history.
- Current patient information is shown for `occupied` and `vacating` states.
- Historical admission context remains available for `cleaning` and `available`, but it is not represented as current ownership.
- Sensitive demographics and clinical notes are excluded.

## Error Contract

- Missing bed/admission/report: `404` where the target resource does not exist.
- Unauthorized role: `403`.
- Invalid, stale, or inconsistent state: `409` with a controlled message.
- Request validation: existing `422` contract.
- Provider, database, or stack details are never returned.

## Frontend

### Bed Management

Replace the hardcoded `/beds` page with API data.

- Title: `Bed Management`.
- Summary cards: Total, Occupied, Vacating, Cleaning, Available, Reserved.
- Filters: ward, status, and search by bed number, patient name, or patient code.
- Table columns: Ward, Bed, Status, Current Patient, Patient ID, Diagnosis, Last Updated, Action.
- Status badges always include text.
- Available rows display an em dash for current patient and `Ready for assignment`.
- Data refetches after every action. No WebSockets or second state system are introduced.

### Bed Detail

Add `/beds/{bedId}` using the existing router. It shows bed identity/status, operational patient/admission context, transition history, and the valid action for the current state.

Actions and confirmations:

- Eligible occupied: `Start Bed Release` → explains `Occupied → Vacating`.
- Vacating: `Confirm Patient Departed` → explains assignment removal and `Cleaning`.
- Cleaning: `Mark Cleaning Complete` → explains the bed becomes available.
- Available: no mutation; show `Ready for assignment`.

Use an accessible reusable confirmation dialog with initial focus, focus containment, Escape/cancel while idle, and disabled dismissal during submission.

### Existing Pages

- Approved discharge report with an eligible occupied bed shows `Report Approved`, `Next Step: Start Bed Release`, and a permitted action linking to or invoking the bed workflow.
- Patient profile shows `Discharge Report Approved — Bed Release Pending`, the current bed status when vacating, and the discharged admission after departure.
- Dashboard bed summary uses real bed API counts. Existing unrelated mocked transfer metrics are not expanded in Feature 4.
- Replace wording that claims n8n automatically releases beds with current manual-workflow wording.

## Testing

Backend tests cover:

- bed list and status/ward filters;
- bed detail and transition history;
- approved and unapproved start-release eligibility;
- occupied → vacating;
- vacating → cleaning plus assignment clearing and admission discharge;
- cleaning → available with no assignment;
- forbidden transition paths;
- available bed rejection;
- start-release idempotency and event uniqueness;
- stale/concurrent requests using independent sessions;
- role enforcement;
- atomic rollback when event or related-record persistence fails;
- exact audit payloads and event counts.

Frontend tests cover API helpers, summary counts, filtering/action derivation, and safety copy using the existing test stack. Full interaction, confirmation accessibility, persistence after refresh, and the complete operational sequence are browser-verified against PostgreSQL.

## Database and Migration

No schema migration is expected because existing enums, assignment fields, timestamps, admission state, and JSON workflow events support the design. If implementation proves a database uniqueness constraint is required for safe event idempotency, add an in-place Alembic migration; never reset existing PostgreSQL data.

## Completion Criteria

Using a synthetic patient with an approved discharge report:

```text
occupied → vacating → cleaning → available
```

must work through the real UI and API. Refreshing after every transition must preserve the state. PostgreSQL must show consistent bed assignment, discharged admission only after departure, and exactly one audit record per defined transition event. No Feature 5 behavior is implemented.
