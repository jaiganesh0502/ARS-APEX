# n8n Workflow Orchestration & Event-Driven Automation

This document specifies the event-driven workflow integration connecting FastAPI backend domain events (`WorkflowEvent`) to n8n webhooks and secure internal service APIs (`/api/internal/*`).

---

## 1. Architectural Principles & Responsibilities

| Layer | Component | Responsibility |
| :--- | :--- | :--- |
| **Source of Truth** | **FastAPI + PostgreSQL** | Clinical decisions, validation rules, state machines, patient charts, capacity reservations, database transactions. |
| **Orchestrator** | **n8n** | Event sequencing, branching, parallel triggers, retries, notification fanout. **n8n NEVER writes directly to PostgreSQL.** |

---

## 2. Event-to-Workflow-to-API Mapping

| Trigger Event | n8n Blueprint | Internal Action Triggered | Human / System Boundary |
| :--- | :--- | :--- | :--- |
| `report_approved` | `01-discharge-orchestration.json` | **Branch A**: `POST /api/internal/beds/{id}/start-release`<br>**Branch B**: `POST /api/internal/admissions/{id}/billing-clearance` | **Parallel**: Bed transitions immediately to `vacating`. Billing clearance initialized as `pending`. |
| `clinical_transfer_decision_confirmed` | `02-transfer-matching.json` | `POST /api/internal/admissions/{id}/start-transfer-matching` | **STOP**: Matches ranked. Attending doctor manually selects facility. |
| `receiving_hospital_selected` | `03-transfer-packet.json` | `POST /api/internal/transfers/{id}/prepare-packet`<br>`POST /api/internal/transfers/{id}/send-packet` | **STOP**: Packet delivered to queue. Receiving physician evaluates. |
| `receiving_hospital_accepted` | `04-transfer-acceptance.json` | **Emergency**: `POST /api/internal/transfers/{id}/dispatch-ambulance`<br>**Non-Emergency**: Dispatch + `POST /api/internal/admissions/{id}/billing-clearance` | **Emergency bypasses billing gate**. Non-emergency tracks billing in parallel. |
| `ambulance_dispatch_requested` | `05-ambulance-dispatch.json` | `POST /api/internal/workflow-events/{id}/complete` | Telemetry sync & ETA notification. |
| `patient_transfer_started` | `06-transfer-departure.json` | Verifies origin bed turnover (`cleaning`). | Physical departure confirms bed release. |
| `billing_cleared` | `07-billing-clearance.json` | `POST /api/internal/billing-clearances/{id}/finalize-handoff` | Emits `final_discharge_authorized` upon doctor approval + billing cleared. |

---

## 3. Webhook & Internal Security

1. **FastAPI $\to$ n8n Webhook**:
   - Header: `X-Workflow-Secret: <N8N_WEBHOOK_SECRET>`
   - Payload: `{"event_id": int, "event_type": str, "entity_type": str, "entity_id": int, "payload": dict, "created_at": str}`
2. **n8n $\to$ FastAPI Internal Endpoints (`/api/internal/*`)**:
   - Header: `X-Internal-API-Key: <INTERNAL_API_KEY>`
   - Unauthenticated requests are rejected with `HTTP 403 Forbidden`.

---

## 4. Delivery Status vs. Orchestration Status

`WorkflowEvent` maintains distinct tracking states:
- **`delivery_status`** (`pending`, `delivered`, `failed`): Indicates if FastAPI reached n8n via HTTP.
- **`orchestration_status`** (`pending`, `processing`, `completed`, `failed`): Reported back by n8n via `/api/internal/workflow-events/{id}/complete` or `/fail`.

---

## 5. Local Setup & Importing Workflows

1. Start development containers:
   ```bash
   docker-compose up -d postgres n8n
   ```
2. Open n8n web interface at **`http://localhost:5678`**.
3. In n8n: **Settings** $\to$ **Import Workflow** $\to$ Select JSON files from `workflows/n8n/`:
   - `01-discharge-orchestration.json`
   - `02-transfer-matching.json`
   - `03-transfer-packet.json`
   - `04-transfer-acceptance.json`
   - `05-ambulance-dispatch.json`
   - `06-transfer-departure.json`
   - `07-billing-clearance.json`
4. Set environment variables in n8n or docker-compose:
   - `N8N_WEBHOOK_SECRET=change-me-in-production`
   - `INTERNAL_API_KEY=change-me-in-production`
   - `FASTAPI_INTERNAL_URL=http://backend:8000/api/internal` (or `http://host.docker.internal:8000/api/internal`)
