# Feature 4 Bed Release and Bed Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn an approved discharge into a safe, auditable `occupied → vacating → cleaning → available` bed workflow with real APIs and UI.

**Architecture:** A dedicated `BedReleaseService` owns all transition, eligibility, locking, conditional-update, event, and transaction behavior. Read APIs expose operational projections; React pages consume them through the existing Axios/local-state pattern and refetch after mutations.

**Tech Stack:** FastAPI, SQLAlchemy 2, PostgreSQL 16, Pydantic 2, pytest, React 18, TypeScript, Axios, Vitest, Tailwind CSS.

**Spec:** `docs/superpowers/specs/2026-08-19-bed-release-management-design.md`

## Global Constraints

- Normal transitions are exactly `occupied → vacating → cleaning → available`.
- Report approval never changes the bed automatically.
- Admission changes `discharging → discharged` only at confirmed patient departure.
- Doctors and ward administrators may perform transitions; actor identity is server-derived.
- Every transition is transactional, concurrency-safe, and audited through internal `WorkflowEvent` rows.
- No n8n execution, transfer departure, hospital matching, ambulance, notification, reservation workflow, WebSocket, or Feature 5 code.
- Never reset PostgreSQL data.
- The workspace has no Git metadata; replace commit steps with progress-ledger entries and independent review gates.

---

### Task 1: Operational Bed Schemas and Read API

**Files:**
- Modify: `backend/app/schemas/bed.py`
- Modify: `backend/app/api/routes/beds.py`
- Create: `backend/app/services/bed_query_service.py`
- Create: `backend/tests/test_bed_queries.py`

**Interfaces:**
- Produces: `BedSummary`, `BedDetail`, `BedTransitionEventRead`, and `BedQueryService.list_beds/get_bed`.
- Consumes: existing `Bed`, `Admission`, `Patient`, `DischargeReport`, and `WorkflowEvent` models.

- [ ] **Step 1: Write failing list/filter/detail tests**

Add tests that seed occupied, vacating, cleaning, available, and reserved beds, then assert:

```python
response = client.get("/api/beds", params={"status": "occupied", "ward": "General Medicine"})
assert response.status_code == 200
assert [item["status"] for item in response.json()] == ["occupied"]
assert response.json()[0]["patient_code"] == "PT-1001"

detail = client.get(f"/api/beds/{bed_id}")
assert detail.status_code == 200
assert detail.json()["admission_id"] == admission_id
assert detail.json()["primary_diagnosis"] == "Community Acquired Pneumonia"
```

- [ ] **Step 2: Verify RED**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_bed_queries.py -q`

Expected: failures because operational response fields and detail route do not exist.

- [ ] **Step 3: Add schemas and query service**

Define explicit projections:

```python
class BedSummary(BaseModel):
    id: int
    ward: str
    bed_number: str
    status: BedStatus
    current_patient_id: int | None
    patient_name: str | None
    patient_code: str | None
    admission_id: int | None
    admission_status: AdmissionStatus | None
    primary_diagnosis: str | None
    release_eligible: bool
    updated_at: datetime

class BedTransitionEventRead(BaseModel):
    event_type: str
    previous_status: BedStatus
    new_status: BedStatus
    created_at: datetime

class BedDetail(BedSummary):
    transition_history: list[BedTransitionEventRead]
```

`BedQueryService` must select the current assignment for occupied/vacating beds, retain the most recent historical admission for cleaning/available detail, calculate eligibility only from approved report plus `report_approved` event, and return events ordered newest first.

- [ ] **Step 4: Replace list response and add detail route**

Keep exact enum/ward filters and pagination. Add:

```python
@router.get("/{bed_id}", response_model=BedDetail)
def get_bed_detail(bed_id: int, db: Session = Depends(get_db)):
    return BedQueryService(db).get_bed(bed_id)
```

- [ ] **Step 5: Verify GREEN**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_bed_queries.py -q`

Then run: `backend\.venv\Scripts\python.exe -m pytest backend/tests -q`

- [ ] **Step 6: Record and review**

Append exact results to `.superpowers/sdd/2026-08-19-bed-release-management/progress.md`; request an independent Task 1 review.

---

### Task 2: Start-Release Service and Endpoint

**Files:**
- Create: `backend/app/services/bed_release_service.py`
- Modify: `backend/app/api/routes/beds.py`
- Create: `backend/tests/test_bed_release_start.py`

**Interfaces:**
- Produces: `BedReleaseService.start_release(bed_id: int, actor: User) -> Bed`.
- Consumes: Task 1 schemas and existing server-derived auth dependency.

- [ ] **Step 1: Write failing eligibility, transition, role, event, and idempotency tests**

Required assertions include:

```python
result = service.start_release(bed.id, ward_admin)
assert result.status is BedStatus.VACATING
assert result.current_patient_id == patient.id
assert admission.status is AdmissionStatus.DISCHARGING
assert event_types(db, bed.id) == ["bed_release_started"]

second = service.start_release(bed.id, ward_admin)
assert second.status is BedStatus.VACATING
assert event_types(db, bed.id) == ["bed_release_started"]
```

Also assert unapproved report, missing `report_approved` event, available bed, mismatched patient/admission, and unauthorized role are rejected without mutation.

- [ ] **Step 2: Verify RED**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_bed_release_start.py -q`

- [ ] **Step 3: Implement atomic start transition**

The method must:

```python
bed = locked_bed(bed_id)
validate_actor(actor)
if consistent_existing_release(bed):
    return bed
validate_approved_discharge_context(bed)
result = db.execute(
    update(Bed)
    .where(Bed.id == bed.id, Bed.status == BedStatus.OCCUPIED)
    .values(status=BedStatus.VACATING)
)
if result.rowcount != 1:
    raise BedTransitionConflict("Bed status changed; refresh and retry")
add_transition_event("bed_release_started", ...)
db.commit()
```

Use one commit and rollback on any exception. Event payload must include bed, patient, admission, report, old/new states, UTC timestamp, and actor fields.

- [ ] **Step 4: Add route**

```python
@router.post("/{bed_id}/start-release", response_model=BedDetail)
def start_release(bed_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user_stub)):
    BedReleaseService(db).start_release(bed_id, actor)
    return BedQueryService(db).get_bed(bed_id)
```

Translate typed not-found, forbidden, and conflict errors to 404/403/409 without stack details.

- [ ] **Step 5: Verify GREEN and full backend**

Run focused test, then `backend\.venv\Scripts\python.exe -m pytest backend/tests -q`.

- [ ] **Step 6: Record and review**

Append results and request independent review of authorization, eligibility, event uniqueness, rollback, and concurrency behavior.

---

### Task 3: Departure and Cleaning Completion

**Files:**
- Modify: `backend/app/services/bed_release_service.py`
- Modify: `backend/app/api/routes/beds.py`
- Create: `backend/tests/test_bed_release_completion.py`

**Interfaces:**
- Produces: `patient_departed(bed_id, actor) -> Bed` and `cleaning_complete(bed_id, actor) -> Bed`.
- Consumes: Task 2 transition/event helpers.

- [ ] **Step 1: Write failing transition and rollback tests**

Assert:

```python
cleaning_bed = service.patient_departed(bed.id, ward_admin)
assert cleaning_bed.status is BedStatus.CLEANING
assert cleaning_bed.current_patient_id is None
assert admission.status is AdmissionStatus.DISCHARGED
assert event_types(db, bed.id) == [
    "bed_release_started", "patient_departed_bed", "bed_cleaning_started"
]

available_bed = service.cleaning_complete(bed.id, ward_admin)
assert available_bed.status is BedStatus.AVAILABLE
assert available_bed.current_patient_id is None
```

Add invalid `occupied → cleaning`, `vacating → available`, available-repeat, stale independent-session, and forced-event-failure rollback tests.

- [ ] **Step 2: Verify RED**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_bed_release_completion.py -q`

- [ ] **Step 3: Implement departure transaction**

Lock bed and admission, validate consistent `vacating`/`discharging` ownership, conditionally update both rows, clear only `Bed.current_patient_id`, preserve `Admission.bed_id`, add two events, and commit once.

- [ ] **Step 4: Implement cleaning-complete transaction**

Require `cleaning` and null current patient, conditionally update to `available`, add one event, and commit once.

- [ ] **Step 5: Add endpoints**

Add `POST /{bed_id}/patient-departed` and `POST /{bed_id}/cleaning-complete`, using the same role/error boundary as Task 2.

- [ ] **Step 6: Remove bypass route**

Remove `PATCH /beds/{bed_id}/status` from normal API exposure or make it reject all turnover transitions. Delete unused `BedUpdateStatus` if no consumer remains.

- [ ] **Step 7: Verify and review**

Run focused and full backend suites. Request independent review of state integrity, rollback, and forbidden paths.

---

### Task 4: Frontend Bed API, Types, and Pure State Helpers

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/beds.ts`
- Create: `frontend/src/features/beds/bedState.ts`
- Create: `frontend/src/features/beds/bedState.test.ts`
- Modify: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces: `listBeds`, `getBed`, `startBedRelease`, `confirmPatientDeparted`, `completeBedCleaning`, `summarizeBeds`, `filterBeds`, and `bedAction`.
- Consumes: Task 1–3 response contracts.

- [ ] **Step 1: Write failing helper and request-contract tests**

```typescript
expect(summarizeBeds(beds)).toEqual({ total: 5, occupied: 1, vacating: 1, cleaning: 1, available: 1, reserved: 1 })
expect(bedAction(eligibleOccupied)).toBe('start_release')
expect(bedAction(ineligibleOccupied)).toBeUndefined()
expect(filterBeds(beds, { ward: 'General Medicine', status: 'occupied', search: 'arun' })).toHaveLength(1)
```

- [ ] **Step 2: Verify RED**

Run: `npm test -- src/features/beds/bedState.test.ts src/api/client.test.ts`

- [ ] **Step 3: Implement exact types and API helpers**

Define `BedSummary`, `BedDetail`, `BedTransitionEvent`, `BedCounts`, `BedAction`, and filter types. API helpers must use the existing `apiClient` and return `response.data`.

- [ ] **Step 4: Implement pure state helpers**

Only eligible occupied beds expose start-release; vacating exposes departure; cleaning exposes completion; available/reserved expose no mutation.

- [ ] **Step 5: Verify frontend tests, lint, and build**

Run `npm test`, `npm run lint`, and `npm run build` from `frontend`.

- [ ] **Step 6: Record and review**

Request review of contract fidelity, null handling, and action gating.

---

### Task 5: Bed Management and Detail UI

**Files:**
- Rewrite: `frontend/src/pages/BedsPage.tsx`
- Create: `frontend/src/pages/BedDetailPage.tsx`
- Create: `frontend/src/features/beds/BedTransitionModal.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/features/beds/bedPresentation.test.tsx`

**Interfaces:**
- Consumes: Task 4 API/helpers.
- Produces: live `/beds` dashboard and `/beds/:bedId` detail workflow.

- [ ] **Step 1: Write failing presentation tests**

Server-render components and assert text labels for all six summary cards, table columns, available-bed placeholder, three confirmation messages, dialog semantics, and status-specific action labels.

- [ ] **Step 2: Verify RED**

Run: `npm test -- src/features/beds/bedPresentation.test.tsx`

- [ ] **Step 3: Implement live Bed Management page**

Load from the API, display loading/error/retry/empty states, compute counts from returned rows, implement ward/status/search controls, render an accessible table, and navigate rows/actions to detail. Refetch after returning from a transition.

- [ ] **Step 4: Implement detail page and modal**

The detail page loads by route ID, shows operational context/history, and derives one valid action. The modal must disclose exact consequences, focus the first action, trap Tab/Shift+Tab, close on Escape only while idle, restore focus, and block dismissal during submission.

- [ ] **Step 5: Implement mutation/refetch flow**

Call the action-specific API, display controlled errors, close only after success, and replace local state with the returned detail. Refreshing the page must reload persisted state.

- [ ] **Step 6: Verify and review**

Run focused/full frontend tests, lint, and build. Request independent accessibility, stale-response, and safety-copy review.

---

### Task 6: Discharge, Patient, and Dashboard Integration

**Files:**
- Modify: `frontend/src/pages/DischargePage.tsx`
- Modify: `frontend/src/pages/PatientDetailPage.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/features/discharge/reportPresentation.test.tsx`
- Create: `frontend/src/features/beds/bedIntegration.test.tsx`

**Interfaces:**
- Consumes: Task 4 bed API/types and existing patient/report APIs.
- Produces: consistent operational next-step messaging and real bed counts.

- [ ] **Step 1: Write failing integration presentation tests**

Assert approved + eligible occupied shows `Report Approved`, `Next Step: Start Bed Release`, and action; vacating shows `Bed Status: Vacating`; departed/discharged shows no release action; dashboard no longer claims n8n automatically releases beds.

- [ ] **Step 2: Verify RED**

Run the two focused Vitest files.

- [ ] **Step 3: Integrate discharge page**

After approval, load the bed summary/detail for the admission and display the correct next step. Route the action to `/beds/{bedId}`. Preserve the existing patient-switch epoch guard for all new async bed responses.

- [ ] **Step 4: Integrate patient profile**

Add a compact operational status block using existing cards/badges; do not redesign clinical content.

- [ ] **Step 5: Make dashboard bed metrics real**

Load the bed list and calculate occupancy/status copy from actual rows. Leave unrelated transfer and review cards unchanged. Replace automatic-n8n wording with manual internal-workflow wording.

- [ ] **Step 6: Verify and review**

Run full frontend tests, lint, and build. Request review for stale-route isolation and truthful workflow copy.

---

### Task 7: PostgreSQL and Browser End-to-End Verification

**Files:**
- Modify: `docs/api.md`
- Modify: `README.md`
- Modify: `.superpowers/sdd/2026-08-19-bed-release-management/progress.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified Feature 4 and final handoff evidence.

- [ ] **Step 1: Confirm migration requirement**

Inspect Alembic head and model metadata. If no schema changed, record `no migration required`; otherwise create an in-place migration and upgrade PostgreSQL without reset.

- [ ] **Step 2: Run all automated checks**

```powershell
cd C:\alta\backend
.\.venv\Scripts\python.exe -m pytest -q
cd C:\alta\frontend
npm test
npm run lint
npm run build
```

- [ ] **Step 3: Prepare one synthetic eligible case**

Use an existing approved discharge report or create a synthetic approved report through the existing safe flow. Confirm bed is occupied, admission discharging, assignment consistent, and `report_approved` exists.

- [ ] **Step 4: Browser-verify with refresh after each transition**

```text
Bed Management → filter → eligible occupied detail → Start Release
→ refresh and verify Vacating → Confirm Patient Departed
→ refresh and verify Cleaning → Mark Cleaning Complete
→ refresh and verify Available
```

Also verify patient and discharge-page messages, dialog keyboard behavior, and absence of application console errors.

- [ ] **Step 5: Query final PostgreSQL state**

Confirm bed `AVAILABLE`, null `current_patient_id`, admission `DISCHARGED`, preserved admission `bed_id`, and exactly one each of `bed_release_started`, `patient_departed_bed`, `bed_cleaning_started`, and `bed_available`.

- [ ] **Step 6: Update documentation**

Document endpoints, state machine, actor roles, manual workflow, admission timing, errors, and explicit exclusions. Do not claim n8n or automatic release.

- [ ] **Step 7: Final independent review and report**

Request a full spec-compliance and safety review. Fix all Critical/Important issues using TDD and re-review. Report important files, database status, endpoints, transitions, exact checks, UI persistence, audit events, remaining warnings, and synthetic rows. Stop before Feature 5.

---

## Plan Self-Review

- Every Feature 4 requirement maps to Tasks 1–7.
- The unrestricted legacy status endpoint is explicitly removed or constrained.
- Admission discharge timing is fixed at physical departure.
- Concurrency uses both locking and conditional updates.
- Read APIs avoid unnecessary clinical/demographic data.
- UI uses existing Axios/local state and refetch, with no WebSockets or new global store.
- Browser verification includes persistence after refresh and final PostgreSQL audit checks.
- No Feature 5 behavior is included.
