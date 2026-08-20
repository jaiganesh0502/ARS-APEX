# Feature 3 AI-Assisted Discharge Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an unapproved Replicate-backed discharge draft from persisted clinical data, let a doctor edit and explicitly approve it, and atomically record approval without discharging the patient or releasing the bed.

**Architecture:** FastAPI routes delegate to `DischargeService`, which validates the Feature 2 discharge decision, uses a focused clinical-context assembler, calls an injected `LLMClientInterface`, and persists through `DischargeRepository`. `ReplicateLLMClient` is the only vendor-specific unit. The React discharge page consumes a dedicated API module and renders explicit generate, edit, approval-review, and approved states.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Replicate Python SDK, pytest, React 18, TypeScript, Axios, Vitest, Vite.

**Spec:** `docs/superpowers/specs/2026-08-19-ai-discharge-report-design.md`

## Global Constraints

- The Replicate model is exactly `openai/gpt-5.6-luna` unless changed through `LLM_MODEL`.
- The token exists only as `REPLICATE_API_TOKEN` in ignored `backend/.env`; never log, return, or commit it.
- AI output can create only `generated` reports and can never approve a report.
- Only a doctor can explicitly transition `generated|under_review → approved`.
- Feature 3 must not set admission status to `discharged`, modify the bed, release a bed, or call n8n/webhooks.
- Provider failure must not silently produce template content.
- Automated tests use a fake provider and never consume paid Replicate calls.
- All production changes follow red-green-refactor.

---

### Task 1: Replicate configuration and provider adapter

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/integrations/llm/client.py`
- Create: `backend/app/integrations/llm/replicate_client.py`
- Modify: `backend/app/integrations/llm/__init__.py`
- Test: `backend/tests/test_replicate_llm_client.py`

**Interfaces:**
- Consumes: `LLMClientInterface.generate_discharge_summary(patient_context)`.
- Produces: `ReplicateLLMClient.generate_discharge_summary(patient_context) -> str` and typed provider exceptions `LLMConfigurationError`, `LLMProviderError`, `LLMTimeoutError`.

- [ ] **Step 1: Write provider-contract tests**

Use an injected stream function so tests exercise input construction and output assembly without a network call:

```python
def test_replicate_client_builds_safe_input_and_collects_stream():
    captured = {}

    def stream(model, *, input):
        captured.update(model=model, input=input)
        return iter(["DRAFT — ", "REQUIRES PHYSICIAN REVIEW AND SIGN-OFF"])

    client = ReplicateLLMClient(token="test-token", stream=stream)
    result = client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})

    assert captured["model"] == "openai/gpt-5.6-luna"
    assert captured["input"]["reasoning_effort"] == "low"
    assert "use only" in captured["input"]["system_prompt"].lower()
    assert result == "DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF"


def test_replicate_client_rejects_blank_output():
    client = ReplicateLLMClient(token="test-token", stream=lambda *_args, **_kwargs: iter(["  "]))
    with pytest.raises(LLMProviderError):
        client.generate_discharge_summary({"primary_diagnosis": "Pneumonia"})


def test_replicate_client_requires_token():
    with pytest.raises(LLMConfigurationError):
        ReplicateLLMClient(token="")
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
cd C:\alta\backend
.\.venv\Scripts\python.exe -m pytest tests\test_replicate_llm_client.py -q
```

Expected: collection fails because `replicate_client` does not exist.

- [ ] **Step 3: Add settings and dependency**

Add to `Settings`:

```python
REPLICATE_API_TOKEN: str = ""
LLM_MODEL: str = "openai/gpt-5.6-luna"
LLM_REASONING_EFFORT: str = "low"
LLM_VERBOSITY: str = "medium"
LLM_MAX_COMPLETION_TOKENS: int = 3000
```

Replace the existing Gemini default and add a bounded `replicate` dependency to `requirements.txt`.

- [ ] **Step 4: Implement the provider adapter**

Use a synchronous interface because the existing FastAPI route is synchronous and the SDK stream is synchronous:

```python
class LLMClientInterface(ABC):
    @abstractmethod
    def generate_discharge_summary(self, patient_context: dict[str, Any]) -> str:
        raise NotImplementedError


class ReplicateLLMClient(LLMClientInterface):
    def __init__(self, token: str, model: str = "openai/gpt-5.6-luna", stream=None):
        if not token.strip():
            raise LLMConfigurationError("Replicate is not configured")
        self.token = token
        self.model = model
        self._stream = stream or replicate.stream

    def generate_discharge_summary(self, patient_context: dict[str, Any]) -> str:
        events = self._stream(
            self.model,
            input={
                "prompt": json.dumps(patient_context, default=str, sort_keys=True),
                "system_prompt": DISCHARGE_SYSTEM_PROMPT,
                "reasoning_effort": settings.LLM_REASONING_EFFORT,
                "verbosity": settings.LLM_VERBOSITY,
                "max_completion_tokens": settings.LLM_MAX_COMPLETION_TOKENS,
            },
        )
        output = "".join(str(event) for event in events).strip()
        if not output:
            raise LLMProviderError("The generation provider returned no content")
        return output
```

Map SDK timeouts and all other SDK errors to typed exceptions without including token, prompt, or provider response bodies.

- [ ] **Step 5: Run provider tests and the backend suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_replicate_llm_client.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: provider tests pass; existing 26 tests remain green.

---

### Task 2: Report provenance migration and persistence contracts

**Files:**
- Modify: `backend/app/models/discharge_report.py`
- Modify: `backend/app/schemas/discharge_report.py`
- Modify: `backend/app/repositories/discharge_repository.py`
- Create: `backend/alembic/versions/20260819_0003_harden_discharge_reports.py`
- Test: `backend/tests/test_discharge_report_persistence.py`

**Interfaces:**
- Produces: `DischargeReport.generation_provider`, `generation_model`, `effective_content`; `DischargeRepository.get_by_admission_id(admission_id)`.
- Consumes: existing `discharge_reports` table from revision `20260819_0001` and revision chain head `20260819_0002`.

- [ ] **Step 1: Write persistence tests**

```python
def test_effective_content_prefers_doctor_edit(discharge_report):
    discharge_report.generated_content = "AI draft"
    discharge_report.edited_content = "Doctor revision"
    assert discharge_report.effective_content == "Doctor revision"


def test_one_report_per_admission(db_session, discharge_report):
    duplicate = DischargeReport(
        patient_id=discharge_report.patient_id,
        admission_id=discharge_report.admission_id,
        generated_content="second",
        generation_provider="replicate",
        generation_model="openai/gpt-5.6-luna",
        status=DischargeReportStatus.GENERATED,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discharge_report_persistence.py -q
```

Expected: missing provenance/effective-content behavior fails.

- [ ] **Step 3: Implement model and schema changes**

Add:

```python
generation_provider = Column(String(40), nullable=False, default="replicate")
generation_model = Column(String(160), nullable=False)

@property
def effective_content(self) -> str:
    return self.edited_content or self.generated_content
```

Expose `generation_provider`, `generation_model`, `effective_content`, `approving_doctor_name`, timestamps, and audit fields in `DischargeReportRead`. Do not accept status or approval fields from create/edit requests.

- [ ] **Step 4: Create migration `20260819_0003`**

Migration operations:

```python
op.add_column("discharge_reports", sa.Column("generation_provider", sa.String(40), nullable=True))
op.add_column("discharge_reports", sa.Column("generation_model", sa.String(160), nullable=True))
op.execute("UPDATE discharge_reports SET generation_provider='legacy', generation_model='legacy-placeholder' WHERE generation_provider IS NULL")
op.alter_column("discharge_reports", "generation_provider", nullable=False)
op.alter_column("discharge_reports", "generation_model", nullable=False)
op.create_index("uq_discharge_reports_admission", "discharge_reports", ["admission_id"], unique=True)
```

Downgrade drops the unique index and both columns. Do not delete rows.

- [ ] **Step 5: Verify on clean SQLite tests and real PostgreSQL**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discharge_report_persistence.py -q
.\.venv\Scripts\python.exe -m alembic upgrade head
docker exec discharge_orchestration_db psql -U postgres -d discharge_orchestration -c "SELECT version_num FROM alembic_version;"
```

Expected PostgreSQL revision: `20260819_0003`.

---

### Task 3: Clinical context assembly and generation eligibility

**Files:**
- Create: `backend/app/services/discharge_context.py`
- Modify: `backend/app/services/discharge_service.py`
- Modify: `backend/app/api/routes/discharge.py`
- Modify: `backend/app/api/dependencies/` only if a focused LLM dependency module is required
- Test: `backend/tests/test_discharge_generation.py`

**Interfaces:**
- Produces: `build_discharge_context(admission: Admission, decision: ClinicalDecision) -> dict[str, Any]`; `DischargeService.generate_report(admission_id, llm_client) -> DischargeReport`.
- Consumes: `ReplicateLLMClient`, `ClinicalDecisionRepository.get_active_for_admission`, `DischargeRepository.get_by_admission_id`.

- [ ] **Step 1: Write generation service tests with a fake provider**

```python
class FakeLLMClient(LLMClientInterface):
    def __init__(self, output="DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF\nPrimary Diagnosis\nPneumonia"):
        self.output = output
        self.context = None

    def generate_discharge_summary(self, patient_context):
        self.context = patient_context
        return self.output


def test_generate_report_uses_persisted_context_and_never_approves(db_session, confirmed_discharge_case):
    fake = FakeLLMClient()
    report = DischargeService(db_session).generate_report(confirmed_discharge_case.admission.id, fake)

    assert fake.context["patient"]["patient_code"] == confirmed_discharge_case.patient.patient_code
    assert fake.context["decision"]["reason"] == "Stable for discharge"
    assert report.status == DischargeReportStatus.GENERATED
    assert report.approved_by is None
    assert report.admission.status == AdmissionStatus.DISCHARGING
    assert report.admission.bed.status == BedStatus.OCCUPIED
```

Add separate tests for unknown admission, admitted state, transfer decision, unconfirmed decision, duplicate report, and blank output.

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discharge_generation.py -q
```

Expected: `generate_report` and context assembler do not exist.

- [ ] **Step 3: Implement deterministic context assembly**

The returned structure uses literal `"Not documented"` markers:

```python
return {
    "patient": {...},
    "admission": {...},
    "bed": {...} if admission.bed else "Not documented",
    "medical_records": [...],
    "medications": [...],
    "recent_vitals": [...],
    "decision": {
        "reason": decision.reason,
        "notes": decision.notes or "Not documented",
    },
}
```

Sort records deterministically and limit recent vitals to five newest entries.

- [ ] **Step 4: Implement generation eligibility and persistence**

`generate_report` must check, in order:

1. admission exists;
2. status is `DISCHARGING`;
3. active decision exists, is `CONFIRMED`, and type is `DISCHARGE`;
4. no report exists;
5. provider returns nonblank content.

Persist provenance as `replicate` and `settings.LLM_MODEL`. Do not commit until provider generation succeeds.

- [ ] **Step 5: Replace the placeholder route**

Make the route call the service with an injected configured client and map exceptions:

```python
except LLMConfigurationError:
    raise HTTPException(503, "AI generation is not configured")
except LLMTimeoutError:
    raise HTTPException(504, "AI generation timed out")
except LLMProviderError:
    raise HTTPException(502, "AI generation failed")
```

Add `GET /discharge/admissions/{admission_id}/report`, returning `404` when absent.

- [ ] **Step 6: Run focused and full backend tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discharge_generation.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

---

### Task 4: Doctor edit, explicit approval, and atomic audit event

**Files:**
- Modify: `backend/app/services/discharge_service.py`
- Modify: `backend/app/api/routes/discharge.py`
- Modify: `backend/app/schemas/discharge_report.py`
- Test: `backend/tests/test_discharge_review.py`

**Interfaces:**
- Produces: `edit_report(report_id, edited_content)` and `approve_report(report_id, doctor)` with atomic event persistence.
- Consumes: existing development-user dependency and `WorkflowEvent` model.

- [ ] **Step 1: Write review and approval tests**

```python
def test_edit_preserves_ai_output_and_sets_under_review(client, generated_report):
    response = client.put(
        f"/api/discharge/reports/{generated_report.id}/edit",
        json={"edited_content": "Doctor-reviewed discharge content"},
    )
    assert response.status_code == 200
    assert response.json()["generated_content"] == generated_report.generated_content
    assert response.json()["edited_content"] == "Doctor-reviewed discharge content"
    assert response.json()["status"] == "under_review"


def test_approval_is_explicit_atomic_and_does_not_release_bed(client, db_session, generated_report):
    response = client.post(f"/api/discharge/reports/{generated_report.id}/approve", json={"acknowledged": True})
    db_session.refresh(generated_report.admission)
    db_session.refresh(generated_report.admission.bed)

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["approved_at"] is not None
    assert generated_report.admission.status == AdmissionStatus.DISCHARGING
    assert generated_report.admission.bed.status == BedStatus.OCCUPIED
    event = db_session.query(WorkflowEvent).filter_by(entity_type="discharge_report", entity_id=generated_report.id).one()
    assert event.event_type == "report_approved"
```

Also test missing acknowledgement, non-doctor user, approved edit, repeated approval, and rollback when event flush fails.

- [ ] **Step 2: Run and verify RED**

Expected failures: route still trusts `approved_by`, acknowledgement is absent, and approval/event commits are not atomic.

- [ ] **Step 3: Harden schemas and route identity**

Use:

```python
class DischargeReportApprove(BaseModel):
    acknowledged: Literal[True]
    clinical_notes: str | None = None
```

Resolve the development doctor through `get_current_user_stub`; never accept `approved_by` from the request.

- [ ] **Step 4: Make approval transactional**

Set report fields and add `WorkflowEvent` before one commit:

```python
report.status = DischargeReportStatus.APPROVED
report.approved_by = doctor.id
report.approved_at = now
self.db.add(WorkflowEvent(...))
try:
    self.db.commit()
except SQLAlchemyError:
    self.db.rollback()
    raise
```

Validate doctor role, report status, and admission status before mutation.

- [ ] **Step 5: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discharge_review.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

---

### Task 5: Frontend report API and state helpers

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/dischargeReports.ts`
- Create: `frontend/src/features/discharge/reportState.ts`
- Test: `frontend/src/features/discharge/reportState.test.ts`

**Interfaces:**
- Produces: `getAdmissionDischargeReport`, `generateDischargeReport`, `editDischargeReport`, `approveDischargeReport`; `effectiveReportContent(report)` and `availableReportActions(report)`.
- Consumes: existing `apiClient` and report API response.

- [ ] **Step 1: Write state-helper tests**

```typescript
it('uses doctor-edited content when present', () => {
  expect(effectiveReportContent({ ...generatedReport, edited_content: 'Doctor revision' }))
    .toBe('Doctor revision');
});

it('makes approved reports read-only', () => {
  expect(availableReportActions({ ...generatedReport, status: 'approved' }))
    .toEqual({ canEdit: false, canReview: false });
});
```

- [ ] **Step 2: Run and verify RED**

```powershell
cd C:\alta\frontend
npm test -- --run src/features/discharge/reportState.test.ts
```

- [ ] **Step 3: Add precise types and API functions**

`DischargeReport` includes provenance, both content fields, effective content, audit fields, and timestamps. The optional admission report GET uses `suppressErrorLog: true` for its expected `404`.

Approval sends only:

```typescript
{ acknowledged: true, clinical_notes?: string }
```

- [ ] **Step 4: Implement helpers and verify GREEN**

Run focused tests, `npm run lint`, and keep the API layer free of component state.

---

### Task 6: Clinical discharge report page

**Files:**
- Replace: `frontend/src/pages/DischargePage.tsx`
- Create: `frontend/src/features/discharge/ReportSafetyNotice.tsx`
- Create: `frontend/src/features/discharge/ReportReviewModal.tsx`
- Test: `frontend/src/features/discharge/reportPresentation.test.tsx`

**Interfaces:**
- Consumes: patient API, Task 5 report API, report state helpers, existing `Button`, `Card`, `PageHeader`, `Spinner`, and `StatusBadge`.
- Produces: complete no-report, generating, generated, editing, approval-review, and approved UI states.

- [ ] **Step 1: Write presentation tests before page code**

Use server rendering for pure safety/review components:

```typescript
it('states that generated content is unapproved', () => {
  const html = renderToStaticMarkup(<ReportSafetyNotice status="generated" />);
  expect(html).toContain('requires physician review');
  expect(html).not.toContain('bed has been released');
});

it('approval modal states the exact limited consequence', () => {
  const html = renderToStaticMarkup(<ReportReviewModal acknowledged={false} />);
  expect(html).toContain('does not discharge the patient');
  expect(html).toContain('does not release the bed');
});
```

- [ ] **Step 2: Run and verify RED**

Expected: components do not exist.

- [ ] **Step 3: Implement the page state machine**

Use explicit local state:

```typescript
type ViewMode = 'summary' | 'editing' | 'approval_review';
const [mode, setMode] = useState<ViewMode>('summary');
const [generating, setGenerating] = useState(false);
const [saving, setSaving] = useState(false);
const [acknowledged, setAcknowledged] = useState(false);
```

On load, fetch patient then optional report. Never call generation from `useEffect`.

- [ ] **Step 4: Implement generation and editing behavior**

- `Generate AI Draft` calls the generate endpoint only on click.
- While generating, disable duplicate clicks and show restrained progress.
- Generated content renders in `<pre>` or escaped text, never `dangerouslySetInnerHTML`.
- `Edit Draft` initializes from effective content.
- Failed save preserves the editor text.

- [ ] **Step 5: Implement explicit approval behavior**

- `Review for Approval` opens a read-only review state.
- A checkbox acknowledgement gates the approval button.
- A final modal repeats limited consequences.
- Approved state is read-only and displays doctor/time.
- No button claims final discharge, bed release, or n8n execution.

- [ ] **Step 6: Run frontend verification**

```powershell
npm test
npm run lint
npm run build
```

Expected: all commands exit zero.

---

### Task 7: Secret setup, PostgreSQL migration, live Replicate, and end-to-end verification

**Files:**
- Create locally ignored: `backend/.env`
- Modify: `backend/.env.example`
- Modify: `docs/api.md`
- Modify: `README.md` only for Feature 3 setup/status

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified Feature 3 against PostgreSQL and one paid synthetic Replicate generation.

- [ ] **Step 1: Install backend dependency**

```powershell
cd C:\alta\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Do not print environment variables after installation.

- [ ] **Step 2: Write ignored provider configuration**

Update `backend/.env` without displaying the token in tool output. Include non-secret model settings in `.env.example` and document that `REPLICATE_API_TOKEN` is required.

- [ ] **Step 3: Apply migration without resetting data**

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
docker exec discharge_orchestration_db psql -U postgres -d discharge_orchestration -c "SELECT version_num FROM alembic_version;"
```

Expected: `20260819_0003`.

- [ ] **Step 4: Run all automated checks**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd C:\alta\frontend
npm test
npm run lint
npm run build
```

- [ ] **Step 5: Perform one live synthetic Replicate generation**

Use a seeded patient with a confirmed discharge decision and `discharging` admission. Confirm:

- provider returns nonblank draft;
- draft starts with or contains the mandatory review warning;
- report is `generated` and unapproved;
- token and full prompt are absent from logs/output;
- admission remains `discharging`;
- bed remains `occupied`.

Do not approve this first live report until the UI review flow is visually verified.

- [ ] **Step 6: Browser-verify the complete workflow**

Verify:

```text
patient → discharge report → explicit Generate AI Draft
→ generated warning → edit → save under_review
→ approval review → acknowledgement → final modal → approve
→ approved read-only state
```

Check the browser console for errors and confirm the UI never claims final discharge or bed release.

- [ ] **Step 7: Verify PostgreSQL audit and safety state**

Query the report, admission, bed, and event:

```sql
SELECT dr.status, dr.generation_provider, dr.generation_model,
       dr.approved_by, dr.approved_at, a.status AS admission_status, b.status AS bed_status
FROM discharge_reports dr
JOIN admissions a ON a.id = dr.admission_id
LEFT JOIN beds b ON b.id = a.bed_id
WHERE dr.id = :report_id;

SELECT event_type, entity_type, entity_id, status
FROM workflow_events
WHERE entity_type = 'discharge_report' AND entity_id = :report_id;
```

Expected: report `APPROVED`, admission `DISCHARGING`, bed `OCCUPIED`, exactly one `report_approved` event.

- [ ] **Step 8: Report completion and stop**

Report changed files, migration result, endpoints, exact test/build results, live provider outcome, safety-state verification, remaining dependency warnings, and any synthetic rows created. Do not implement Feature 4.

---

## Plan Self-Review

- Every approved specification requirement maps to a task.
- Provider calls are isolated and fakeable.
- No automated test consumes Replicate credits.
- Approval identity comes from the backend dependency, not the request body.
- Report approval and workflow event use one transaction.
- PostgreSQL data is migrated in place.
- Frontend cannot auto-generate or auto-approve.
- Feature 4 actions remain excluded.
