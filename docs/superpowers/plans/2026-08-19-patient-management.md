# Patient Management and Synthetic Patient Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PostgreSQL-backed patient directory and clinical profile for eight synthetic patients, exposed through FastAPI and rendered by React without frontend fallback data.

**Architecture:** Extend the existing ORM and patient route through repository and service layers. The repository owns joined/eager-loaded queries, the service selects the active admission and maps typed schemas, and React consumes the paginated/detail contracts through the shared Axios client.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic, PostgreSQL 16, pytest, React 18, TypeScript, Vite, Tailwind CSS, Axios.

**Spec:** `docs/superpowers/specs/2026-08-19-patient-management-design.md`

## Global Constraints

- Preserve existing unrelated routes, models, integrations, and the discharge placeholder.
- Never auto-finalize clinical content or add Feature 2 behavior.
- All patient UI data must come from the FastAPI API; no React fallback patient data.
- Seed data must be fictional, repeatable, and idempotent.
- Avoid cascading deletion of clinical history.
- Use `GET /api/patients` with `{items,page,page_size,total}` and `GET /api/patients/{id}` for detail.

---

### Task 1: Patient API contract and query behavior

**Files:**
- Create: `backend/tests/test_patients.py`
- Modify: `backend/app/schemas/patient.py`
- Modify: `backend/app/repositories/patient_repository.py`
- Create: `backend/app/services/patient_service.py`
- Modify: `backend/app/api/routes/patients.py`
- Modify: `backend/app/models/patient.py`
- Modify: `backend/app/models/admission.py`

**Interfaces:**
- Produces: `PatientRepository.list_page(page, page_size, search, status) -> tuple[list[Patient], int]`.
- Produces: `PatientRepository.get_detail(patient_id) -> Patient | None`.
- Produces: `PatientService.list_patients(...) -> PatientListResponse` and `PatientService.get_patient(patient_id) -> PatientDetail`.
- Produces: `PatientSummary`, `PatientListResponse`, `PatientDetail`, and nested detail schemas.

- [ ] **Step 1: Write failing API tests**

Create fixtures for a doctor, two beds, patients, admissions, medical records, medications, and timestamped vitals. Assert pagination envelope, case-insensitive code/name search, status filtering, complete detail, newest-first vitals limited to five, 404, and invalid pagination 422.

- [ ] **Step 2: Run tests and confirm contract failures**

Run: `python -m pytest tests/test_patients.py -v`

Expected: failures because current routes return `list[PatientRead]`, lack status filtering/detail schemas, and expose no service.

- [ ] **Step 3: Add typed Pydantic response models**

Define summary and detail schemas with the exact JSON property names in the specification. Make absent admission, doctor, bed, and medical record fields nullable while medications and vitals default to empty lists.

- [ ] **Step 4: Implement repository queries**

Use SQLAlchemy `joinedload`/`selectinload` for admission, doctor, bed, medical records, medications, and vitals. Apply `ilike` search and admission-status filters in SQL, count distinct patients, order by patient code and ID, and paginate with offset/limit.

- [ ] **Step 5: Implement service mapping**

Select the latest admission by `(admission_date, id)`, calculate age correctly relative to today's month/day, select the newest medical record, and sort vitals by `(recorded_at, id)` descending with a five-item limit.

- [ ] **Step 6: Replace route logic with service calls**

Validate `page >= 1`, `1 <= page_size <= 100`, and optional `AdmissionStatus`. Catch `SQLAlchemyError`, log it, roll back the session, and return generic HTTP 500 detail. Preserve patient creation behavior behind its current route.

- [ ] **Step 7: Run backend patient tests**

Run: `python -m pytest tests/test_patients.py -v`

Expected: all patient endpoint tests pass.

### Task 2: Reproducible migration and synthetic dataset

**Files:**
- Create: `backend/alembic/versions/20260819_0001_initial_schema.py`
- Modify: `backend/app/db/seed.py`
- Modify: `data/synthetic/patients.json`
- Modify: `README.md`
- Create or modify: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: existing SQLAlchemy `Base.metadata` and Feature 1 model constraints.
- Produces: `seed_database(db: Session | None = None) -> None`, safe to call repeatedly.
- Produces: eight patients `PT-1001` through `PT-1008`, each with one admission, bed, record, medication(s), and at least two vitals.

- [ ] **Step 1: Write failing seed idempotency test**

Call `seed_database(db_session)` twice. Assert exactly eight `PT-100x` patients and unchanged counts for their admissions, records, medications, and vitals after the second call.

- [ ] **Step 2: Run the seed test and confirm failure**

Run: `python -m pytest tests/test_seed.py -v`

Expected: failure because the current seed skips based on any user and does not upsert individual records.

- [ ] **Step 3: Replace the synthetic JSON dataset**

Write eight fictional cases matching the requested diagnoses/statuses. Each case includes demographics, a named ward/bed, one medical record, one to four medications, and two or more ISO-8601 vitals.

- [ ] **Step 4: Make seeding record-idempotent**

Get or create users by email, hospitals by name, capacities by hospital/specialty, beds by ward/number, and patients by patient code. For each patient, get or create the active admission and add missing dependents by stable field tuples. Set bed status and current patient consistently. Use a transaction and rollback on error. Remove `Base.metadata.create_all()` from CLI execution.

- [ ] **Step 5: Add the baseline Alembic revision**

Create all existing application tables in dependency order with indexes, constraints, reversible foreign keys, and downgrade in reverse order. Use restrictive foreign keys for clinical-history rows so patient/admission deletion cannot silently erase them.

- [ ] **Step 6: Document migration and seed commands**

Document `alembic upgrade head` followed by `python -m app.db.seed`; remove instructions that generate an initial revision or invoke the seed file directly.

- [ ] **Step 7: Run seed tests**

Run: `python -m pytest tests/test_seed.py tests/test_patients.py -v`

Expected: all tests pass.

### Task 3: Typed React patient data layer

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/patients.ts`

**Interfaces:**
- Produces: `PatientSummary`, `PatientListResponse`, `PatientDetail`, `PatientDemographics`, `PatientAdmissionDetail`, `PatientBedDetail`, `MedicalRecord`, `Medication`, and `Vital`.
- Produces: `getPatients(params: PatientListParams): Promise<PatientListResponse>`.
- Produces: `getPatientById(patientId: number): Promise<PatientDetail>`.

- [ ] **Step 1: Define API-aligned TypeScript types**

Add paginated summary and nested detail types. Retain types required by unrelated pages and avoid `any`.

- [ ] **Step 2: Add patient API functions**

Reuse `apiClient`, map camel-case function parameters to `page_size`, omit empty search/status parameters, and return `response.data`.

- [ ] **Step 3: Run TypeScript check to expose page contract mismatches**

Run: `npm run lint`

Expected: patient pages fail until Task 4 consumes the new types and service.

### Task 4: Patient directory and profile UI

**Files:**
- Modify: `frontend/src/pages/PatientsPage.tsx`
- Modify: `frontend/src/pages/PatientDetailPage.tsx`
- Modify: `frontend/src/components/common/StatusBadge.tsx` if required for all admission states.

**Interfaces:**
- Consumes: `getPatients`, `getPatientById`, `PatientSummary`, and `PatientDetail` from Task 3.
- Preserves: `/patients`, `/patients/:patientId`, and `/patients/:patientId/discharge` routing in `App.tsx`.

- [ ] **Step 1: Implement server-driven patient directory state**

Fetch page 1 with page size 20; refetch on search/status changes; reset page on filters; render patient count, explicit status text, loading indicator, `No patients found.`, safe error copy, and Retry. Remove fallback arrays and client-side fake statuses.

- [ ] **Step 2: Implement responsive directory table**

Render patient code, name, age/gender, diagnosis, ward/bed, status, and only `View Patient`. Wrap table overflow for smaller screens.

- [ ] **Step 3: Implement API-backed profile loading states**

Validate numeric route ID, fetch detail, handle loading, 404/general failure, Retry, and back navigation without rendering stale placeholder content.

- [ ] **Step 4: Implement clinical profile sections**

Render demographics, admission/doctor, bed, diagnosis/treatment/notes, latest five vitals, and medications. Display null medication end date as `Ongoing`. Preserve multiline clinical copy with whitespace-aware styling.

- [ ] **Step 5: Add the single primary action**

Render `Start Discharge / Transfer` and navigate to `/patients/{id}/discharge`; do not add editing or other fake actions.

- [ ] **Step 6: Run frontend verification**

Run: `npm run lint`

Run: `npm run build`

Expected: both commands exit successfully.

### Task 5: PostgreSQL and end-to-end verification

**Files:**
- Modify only if verification exposes an in-scope defect.

**Interfaces:**
- Consumes all prior tasks.
- Produces fresh evidence for the Feature 1 completion report.

- [ ] **Step 1: Run the complete backend test suite**

Run: `python -m pytest -v`

Expected: all tests pass with zero failures.

- [ ] **Step 2: Start PostgreSQL and apply migration**

Run from repository root: `docker compose up -d postgres`

Run from `backend`: `alembic upgrade head`

Expected: PostgreSQL becomes healthy and migration reaches `20260819_0001`.

- [ ] **Step 3: Seed twice and verify row counts**

Run twice from `backend`: `python -m app.db.seed`

Query counts for `PT-1001`–`PT-1008`, admissions, medical records, medications, and vitals. Expected: eight patient codes with no duplicate dependent rows after the second run.

- [ ] **Step 4: Verify live API responses**

Start Uvicorn and request `/api/health`, `/api/patients`, `/api/patients?search=pt-1001`, `/api/patients?status=transfer_pending`, and a seeded patient detail. Expected: successful typed responses and safe 404 for an unknown ID.

- [ ] **Step 5: Re-run frontend checks**

Run: `npm run lint` and `npm run build` from `frontend`.

Expected: both exit successfully.

- [ ] **Step 6: Report exact evidence and remaining problems**

List important files, migration revision, seeded counts, endpoints, exact test/build results, frontend behavior, and any infrastructure limitation. Stop before Feature 2.
