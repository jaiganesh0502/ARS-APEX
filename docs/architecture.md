# Hospital Discharge & Transfer Orchestration Architecture

## 1. System Overview

The **AI-Powered Hospital Discharge Orchestration System** is a clinical workflow platform for discharge-report review and controlled operational bed turnover. Inter-hospital matching, ambulance coordination, notifications, and external orchestration are planned capabilities, not current Feature 4 behavior.

### Key Architecture Principle
- **FastAPI owns**: Patient records, Electronic Health Records (EHR), bed occupancy, discharge report drafts, the UI/API, **Doctor Review & Explicit Approval**, and the manual Feature 4 bed-turnover service.
- **n8n is future-only**: workflow definitions and integration contracts may be retained for future orchestration, but no current Feature 4 action publishes a webhook, calls n8n, or automates bed turnover.

```text
[ Clinician / Doctor ]
        │
        ▼ (Triggers Draft Generation)
[ AI LLM Engine ] ──► [ Draft Discharge Report ] (Status: generated)
                                │
                                ▼
                        [ Doctor Review & Edit ]
                                │
                                ▼ (Explicit Approval ONLY)
                        [ Clinical Approval ] ──► (Status: approved)
                                │
                                │
                                ▼
               [ Internal pending report_approved event ]
                                │
                                ▼
      [ Authorized staff manually start eligible bed release ]
                                │
                                ▼
       [ occupied -> vacating -> cleaning -> available ]

[ Future, not invoked: n8n/webhooks, transfer matching, ambulance dispatch,
  notifications, and other external orchestration ]
```

---

## 2. Clinical Safety Guardrail

> **MANDATORY CLINICAL SAFETY CONSTRAINT**:
> Under no circumstance may an AI-generated draft automatically transition to `approved`.
> 
> The lifecycle of every discharge summary is strictly governed by state transitions:
> `draft` ➔ `generated` ➔ `under_review` ➔ `approved` (signed by an authenticated physician).
> 
> A pending internal `report_approved` audit event is persisted **only** upon valid physician sign-off. It does not trigger n8n, release a bed, discharge an admission, or start external work.

---

## 3. Monorepo Component Boundaries

### Backend (`/backend`)
- **Framework**: FastAPI (Python 3.11+)
- **ORM & DB**: SQLAlchemy 2.0 with PostgreSQL 16
- **Migrations**: Alembic
- **Pattern**: Layered Clean Architecture (Models ➔ Schemas ➔ Repositories ➔ Services ➔ API Routers & Dependencies)
- **Integration Contracts**: Abstract interfaces for an LLM and future n8n, Maps, and notification integrations. These external integrations are not invoked by Feature 4.

### Frontend (`/frontend`)
- **Framework**: React 18, Vite, TypeScript
- **Styling**: Tailwind CSS (calm clinical palette with clear status badges and zero jarring animations)
- **Routing**: React Router v6
- **State & Networking**: Axios client with interceptors, standardized API responses.

### Orchestration Workflows (`/workflows/n8n`)
- Future/planned n8n workflow definitions and diagrams. The current application does not fire FastAPI webhooks into these workflows, and they do not control the Feature 4 bed state machine.

### Synthetic Data (`/data/synthetic`)
- Strict, clearly marked fictional EHR records for validation, testing, and UI demonstration.

---

## 4. Entity State Machines

### Admission Status
```text
admitted ──► discharging ──► discharged
    │
    └──► transfer_pending ──► transferred
```

### Bed Status
```text
occupied ──► vacating ──► cleaning ──► available
```

`reserved` is structurally supported but has no Feature 4 transition. Only an authorized doctor or ward administrator can manually progress the displayed path; direct, skipped, and automated transitions are rejected.

### Discharge Report Status
```text
draft ──► generated ──► under_review ──► approved
```

### Transfer Status
```text
matching ──► awaiting_acceptance ──► accepted ──► ambulance_requested ──► in_transit ──► completed
    │                  │
    └──► cancelled     └──► rejected
```

### Ambulance Dispatch Status
```text
requested ──► en_route ──► arrived ──► patient_onboard ──► completed
```
