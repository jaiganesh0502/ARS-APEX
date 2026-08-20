# Feature 1: Patient Management and Synthetic Patient Data

## Purpose

Deliver a read-only clinical patient directory and patient profile backed end to end by PostgreSQL, FastAPI, SQLAlchemy, and React. The feature establishes the patient context required by later discharge, transfer, and bed-release workflows without implementing those workflows.

## Scope

Feature 1 includes:

- A paginated, searchable, status-filterable patient list API.
- A complete patient-detail API for the active admission.
- Eight clearly fictional patient cases with realistic admissions, beds, medications, vitals, medical records, and clinical notes.
- An idempotent database seed command.
- A responsive patient directory and read-only clinical profile UI.
- Backend tests for list, detail, not-found, search, and status filtering.
- Alembic migration coverage and PostgreSQL verification.

Feature 1 excludes discharge generation, LLM calls, approvals, hospital matching, transfer orchestration, bed-release automation, ambulance dispatch, n8n workflows, maps, messaging, real authentication, and real EHR integration.

## Existing-System Constraints

The repository already contains the required core ORM entities, a patient repository and routes, React patient routes, a shared Axios client, common UI components, PostgreSQL configuration, and Alembic infrastructure. Implementation will extend these components rather than create replacements.

Existing unrelated routes and placeholder integrations remain intact. The existing discharge route at `/patients/:patientId/discharge` remains a placeholder and is only used as the destination of the profile's primary action.

## Backend Design

### Data model

Retain and validate the existing `Patient`, `Admission`, `MedicalRecord`, `Medication`, `Vital`, `Bed`, and `User` models. Required fields and controlled admission states will match the feature request.

Relationships:

- A patient has admissions, medical records, medications, and vitals.
- An admission belongs to a patient and attending doctor, optionally occupies a bed, and has medical records, medications, and vitals.
- A bed may be assigned to the active admission and references its current patient.

Clinical-history collections will not use ORM delete-orphan cascades from patients or admissions. Database foreign keys for medical records, medications, and vitals will prevent accidental deletion of referenced clinical history. This feature does not add a patient-deletion workflow.

### Migration

Create the repository's first Alembic revision as a complete, reproducible baseline for the current SQLAlchemy metadata, including indexes, foreign keys, enum-compatible check behavior, and all existing application tables. Any relationship-safety changes required by Feature 1 will be represented in that migration.

The migration must upgrade a clean PostgreSQL database to the expected schema and provide a downgrade path. Runtime startup and the seed command will not substitute `Base.metadata.create_all()` for migrations.

### Repository and service boundaries

`PatientRepository` owns SQLAlchemy queries. It will:

- Build a patient-list query joined to the current/latest admission and its bed.
- Apply case-insensitive search across patient code, first name, and last name.
- Apply admission-status filtering.
- Return the requested page plus a total count.
- Eager-load the active/latest admission, doctor, bed, medical records, medications, and vitals for detail retrieval.

`PatientService` owns response-oriented business rules. It will:

- Validate that a requested patient exists.
- Select the active/latest admission deterministically by admission date and ID.
- Calculate age from date of birth using the current date.
- Sort vitals newest first and return no more than the latest five.
- Select the newest medical record for the active admission.
- Map database entities into typed summary and detail schemas.

Routes remain thin: validate query/path parameters, invoke the service, and return typed responses. Expected absence produces HTTP 404. Pydantic/FastAPI validation handles invalid pagination with HTTP 422. Unexpected database failures are logged server-side and returned through a controlled generic HTTP 500 response without database details.

## API Contract

### `GET /api/patients`

Query parameters:

- `page`: integer, default `1`, minimum `1`.
- `page_size`: integer, default `20`, minimum `1`, maximum `100`.
- `search`: optional trimmed string.
- `status`: optional controlled admission status.

Response:

```json
{
  "items": [
    {
      "id": 1,
      "patient_code": "PT-1001",
      "first_name": "Arun",
      "last_name": "Kumar",
      "age": 52,
      "gender": "Male",
      "primary_diagnosis": "Community Acquired Pneumonia",
      "admission_status": "admitted",
      "ward": "General Medicine",
      "bed_number": "GM-12"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 8
}
```

Patients without an admission or bed remain representable with nullable admission/bed summary fields. Ordering is stable by patient code and ID.

### `GET /api/patients/{patient_id}`

Return a typed profile containing:

- Patient identity and demographics, including calculated age.
- Active/latest admission, status, diagnosis, and attending-doctor identity.
- Assigned bed and its status.
- Latest medical record for that admission.
- Medications for that admission.
- Up to five latest vitals, newest first.

An unknown patient ID returns HTTP 404 with the application's existing safe error envelope.

## Synthetic Dataset

Seed exactly eight patients with codes `PT-1001` through `PT-1008` and the requested diagnoses/statuses:

1. Community Acquired Pneumonia — admitted, General Medicine.
2. Post-operative Appendectomy — admitted, General Surgery.
3. Type 2 Diabetes with Hyperglycemia — admitted, General Medicine.
4. Acute Ischemic Stroke — transfer pending, Neurology.
5. Femur Fracture — admitted, Orthopedics.
6. Acute Gastroenteritis with Dehydration — discharging.
7. Acute Coronary Syndrome — transfer pending, Cardiology.
8. Urinary Tract Infection — admitted.

Every patient has demographics, one active admission, an occupied or workflow-appropriate bed, at least one medical record, at least one medication, and at least two vitals. Complex cases receive two to four medications. Names, phone numbers, contacts, notes, and all other clinical details are fictional and explicitly intended for demonstration.

The seed process performs natural-key upserts or get-or-create behavior for users, hospitals, capacities, beds, and patients. It adds missing dependent records without duplicating existing ones and commits as a single transaction where practical. It can be run as:

```text
cd backend
python -m app.db.seed
```

It does not create database tables.

## Frontend Design

### Types and API service

Add dedicated TypeScript types for patient summaries, detail, demographics, admission detail, bed detail, medical records, medications, vitals, and paginated results. Reuse the existing admission and bed status unions. No patient data uses `any`.

Add a patient API module that reuses the shared Axios client and exposes:

- `getPatients({ page, pageSize, search, status })`
- `getPatientById(patientId)`

Errors are converted into UI-safe states by the pages; raw Axios messages are not rendered.

### Patient directory

`/patients` displays:

- A `Patients` page heading and patient count.
- A search field whose value is sent to the API.
- A status select with all controlled statuses.
- A horizontally scrollable table on small screens.
- Patient code, name, age/gender, diagnosis, ward/bed, status, and one `View Patient` action.
- A loading skeleton or clear loading indicator before results arrive.
- `No patients found.` when the result is empty.
- A safe error message and `Retry` action when loading fails.

Search and status changes reset pagination to page one. API calls are server-driven; React contains no fallback patient records or client-side substitute dataset.

### Patient profile

`/patients/:patientId` loads the patient-detail API and displays:

- Header: name, patient code, age, gender, blood group, admission status.
- Patient Information card.
- Admission card.
- Bed Information card.
- Current Diagnosis / Medical Record card with readable multiline treatment course and notes.
- Recent Vitals table, newest first, maximum five rows.
- Medications table, with null end dates rendered as `Ongoing`.
- Primary `Start Discharge / Transfer` action linking to the existing `/patients/{patientId}/discharge` placeholder.
- Back navigation, loading state, not-found/general error state, and retry behavior.

The layout prioritizes clinical readability with restrained color, explicit status text, responsive card stacking, and table overflow on tablets. No editing or decorative charts are added.

## Testing

Backend tests use the existing isolated test database setup and seed only the fixtures needed per test. Tests cover:

- Paginated patient list shape and totals.
- Patient detail with admission, bed, doctor, record, medications, and newest-first vitals.
- Unknown patient returning HTTP 404.
- Case-insensitive search by patient code and name.
- Status filtering.
- Invalid pagination returning HTTP 422.
- Idempotent seed behavior where practical.

Frontend verification uses the configured TypeScript check and production build. Manual/API verification confirms search, status filtering, navigation, and profile clinical sections using backend-provided data.

## Verification and Acceptance

Completion requires fresh evidence for:

1. Alembic upgrade succeeds against PostgreSQL.
2. The idempotent seed command succeeds twice and leaves exactly eight `PT-100x` patients.
3. PostgreSQL contains the required tables and related seeded rows.
4. Backend tests pass.
5. `/api/health`, `/api/patients`, and one seeded patient detail return successful responses.
6. Frontend typecheck/lint and production build pass.
7. Patient list, search, status filter, detail routing, medications, vitals, and treatment history work without hardcoded React data.

Any unavailable local infrastructure or failed check is reported explicitly rather than hidden.

## Next Feature Boundary

Stop after Feature 1. Feature 2 is Doctor Decision plus Discharge / Transfer Entry Flow and is not part of this implementation.
