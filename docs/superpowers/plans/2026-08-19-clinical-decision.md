# Clinical Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist, review, and explicitly confirm doctor-selected discharge or transfer decisions, with correct admission state transitions and frontend continuation states.

**Architecture:** Add a `ClinicalDecision` SQLAlchemy entity and repository/service/routes that transact decision confirmation, admission transition, and audit event together. Add a typed React data service and two-step decision page that reuses the Feature 1 patient profile and existing destination placeholders.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic, PostgreSQL 16, pytest, React 18, TypeScript, Vite, Tailwind CSS, Axios.

**Spec:** `docs/superpowers/specs/2026-08-19-clinical-decision-design.md`

## Global Constraints

- Doctor selection is always manual; AI cannot choose discharge or transfer.
- Confirmation changes only the admission and audit log; the bed remains unchanged.
- Do not add report generation, matching, external events, n8n, ambulance, maps, or messaging.
- Reuse the existing database session, development user, Axios client, router, and UI components.
- Preserve Feature 1 behavior and data.
- No more than one non-cancelled clinical decision may exist per admission.

---

### Task 1: Clinical decision domain and migration

**Files:**
- Create: `backend/app/models/clinical_decision.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db/base.py`
- Modify: `backend/app/models/patient.py`
- Modify: `backend/app/models/admission.py`
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/20260819_0002_clinical_decisions.py`

**Interfaces:**
- Produces: `ClinicalDecisionType`, `TransferUrgency`, `ClinicalDecisionStatus`, and `ClinicalDecision`.
- Produces: patient/admission/doctor `clinical_decisions` relationships.

- [ ] **Step 1: Add model metadata tests to `backend/tests/test_clinical_decisions.py`**

Assert controlled enum values, restrictive foreign keys, nullable transfer-only fields, and relationships.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest tests/test_clinical_decisions.py -v`

Expected: import failure because `ClinicalDecision` does not exist.

- [ ] **Step 3: Implement the model and relationships**

Use enum values exactly `discharge|transfer`, `emergency|non_emergency`, and `draft|confirmed|cancelled`; add timezone-aware audit timestamps and restrictive foreign keys.

- [ ] **Step 4: Add migration `20260819_0002`**

Create the table, indexes, foreign keys, enum-compatible values, and PostgreSQL partial unique index for admission rows whose status is `draft` or `confirmed`. Downgrade removes only Feature 2 objects.

- [ ] **Step 5: Run the focused tests**

Run: `python -m pytest tests/test_clinical_decisions.py -v`

Expected: model tests pass.

### Task 2: Schemas, repository, service, and APIs

**Files:**
- Create: `backend/app/schemas/clinical_decision.py`
- Create: `backend/app/repositories/clinical_decision_repository.py`
- Create: `backend/app/services/clinical_decision_service.py`
- Create: `backend/app/api/routes/clinical_decisions.py`
- Modify: `backend/app/api/routes/__init__.py`
- Test: `backend/tests/test_clinical_decisions.py`

**Interfaces:**
- Produces: `ClinicalDecisionCreate`, `ClinicalDecisionUpdate`, `ClinicalDecisionRead`.
- Produces: `ClinicalDecisionRepository.get_active_for_admission(admission_id)` and `get_with_context(decision_id)`.
- Produces: service methods `create_draft`, `get_current`, `update_draft`, and `confirm`.
- Produces the four API endpoints from the spec.

- [ ] **Step 1: Write failing endpoint tests**

Create fixtures for a doctor, patient, admitted admission, and occupied bed. Test discharge, both transfer urgencies, invalid transfer/discharge payloads, unknown admission, retrieval, draft update, confirmed-update rejection, duplicate rejection, both confirmation state changes, unchanged bed, and exact audit events.

- [ ] **Step 2: Run tests and confirm failures**

Run: `python -m pytest tests/test_clinical_decisions.py -v`

Expected: routes return 404 or fail imports.

- [ ] **Step 3: Implement Pydantic cross-field validation**

Trim reason/specialty. Reject empty reason, transfer without urgency/specialty, and discharge with transfer-only fields using `model_validator`.

- [ ] **Step 4: Implement repository reads without independent commits**

Eager-load patient, admission, and deciding doctor. Return newest non-cancelled decision for an admission.

- [ ] **Step 5: Implement service business rules**

Require `admitted` for creation; return 409 for duplicates and invalid lifecycle changes. On confirmation set decision status/time, transition admission, add one `WorkflowEvent`, commit once, refresh, and roll back on failure.

- [ ] **Step 6: Implement thin routes**

Use the shared session and `get_current_user_stub`; return 401 when no user exists, 404 for missing resources, 409 for conflicts, 422 for invalid payloads, and safe 500 errors.

- [ ] **Step 7: Run focused and full backend tests**

Run: `python -m pytest tests/test_clinical_decisions.py -v`

Run: `python -m pytest -v`

Expected: all pass.

### Task 3: Frontend types, API service, and routing

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/clinicalDecisions.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/ClinicalDecisionPage.tsx`

**Interfaces:**
- Produces: TypeScript decision type/status/request interfaces and `CLINICAL_SPECIALTIES`.
- Produces: `createClinicalDecision`, `getClinicalDecision`, `updateClinicalDecision`, and `confirmClinicalDecision`.
- Produces route `/patients/:patientId/decision`.

- [ ] **Step 1: Define API-aligned decision types and specialty constant**

Use exact snake_case API property names and shared union types; do not use `any`.

- [ ] **Step 2: Add decision API functions**

Reuse `apiClient`; preserve 404 status visibility so the page can distinguish no decision from service failure.

- [ ] **Step 3: Add the route and page shell**

Load patient detail, require a current admission, fetch the current decision, and implement loading/error/retry states.

- [ ] **Step 4: Run TypeScript check**

Run: bundled Node `node_modules/typescript/bin/tsc --noEmit`.

Expected: no type errors after the shell is complete.

### Task 4: Two-step clinical decision UI and patient integration

**Files:**
- Modify: `frontend/src/pages/ClinicalDecisionPage.tsx`
- Modify: `frontend/src/pages/PatientDetailPage.tsx`
- Modify: `frontend/src/components/common/StatusBadge.tsx`

**Interfaces:**
- Consumes all Task 3 types and API methods.
- Produces state-aware patient actions and the complete decision/review/confirm flow.

- [ ] **Step 1: Implement accessible decision selection and conditional form**

Add discharge/transfer radio cards, required fields, one specialty select, emergency warning, non-emergency information, and inline validation.

- [ ] **Step 2: Implement review and draft persistence**

Render all entered fields, allow Back to Edit, create or update the draft once before opening the confirmation dialog, and prevent duplicate submissions.

- [ ] **Step 3: Implement confirmation dialog and redirects**

Show exact consequence text, Cancel/Confirm actions, pending state, safe failure copy, and redirect discharge to `/patients/{id}/discharge` or transfer to `/transfers/new?patientId={id}`.

- [ ] **Step 4: Implement existing-decision state**

Populate drafts for editing. Render confirmed decisions read-only with decision metadata and the correct continuation action.

- [ ] **Step 5: Make patient-profile action state-aware**

Route admitted patients to the decision page, discharging patients to discharge, transfer-pending patients to the transfer continuation URL, and hide the start action for terminal statuses.

- [ ] **Step 6: Run frontend verification**

Run TypeScript check and Vite production build. Expected: both exit zero.

### Task 5: Migration, live API, and final verification

**Files:**
- Modify only if a verification failure exposes an in-scope defect.

**Interfaces:**
- Consumes all previous tasks and produces completion evidence.

- [ ] **Step 1: Run the complete backend suite**

Run: `python -m pytest -v`. Expected: zero failures.

- [ ] **Step 2: Verify migration chain without resetting patient data**

Apply `20260819_0001 -> 20260819_0002`, seed, downgrade to `0001`, and upgrade to head in an isolated database. Use PostgreSQL if available; otherwise report that limitation and verify on SQLite.

- [ ] **Step 3: Verify live discharge and transfer API flows**

Create and confirm separate discharge and transfer decisions. Verify admission states, unchanged beds, current-decision reads, duplicate rejection, and internal event payloads.

- [ ] **Step 4: Run frontend typecheck and build again**

Expected: both exit zero.

- [ ] **Step 5: Report exact results and stop before Feature 3**

List changed files, migration, endpoints, test counts, transition evidence, UI states, redirects, and every remaining problem.
