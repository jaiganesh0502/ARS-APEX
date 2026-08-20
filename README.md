# AI-Powered Hospital Discharge & Transfer Orchestration System

A production-grade, extensible clinical workflow platform built for MedTech orchestration.

Features 3 and 4 manage the clinical report and the separate, manual operational
turnover stages:
**Doctor decision ➔ AI-generated discharge report ➔ doctor review and explicit approval ➔ pending internal `report_approved` event ➔ staff-operated bed release**.
Approval never automatically releases a bed, discharges an admission, publishes to
n8n, or starts external orchestration. An authorized doctor or ward administrator
must explicitly progress an eligible bed through `occupied ➔ vacating ➔ cleaning
➔ available`.

---

## 1. System Architecture & Workflows

The platform enforces strict separation of clinical decision-making and automated orchestration:

1. **FastAPI Backend (Synchronous / Clinical Decision Layer)**:
   - Electronic Health Record (EHR) models (Patients, Admissions, Medical Records, Vitals, Medications).
   - Ward Bed status transitions (`available`, `occupied`, `vacating`, `cleaning`, `reserved`).
   - AI draft generation (`status: generated`).
   - **Doctor Review & Explicit Approval** (`status: approved` signed by physician).
   - Records one pending internal `report_approved` event after explicit approval; it does not publish to n8n or release a bed.

2. **Manual Bed Turnover and Planned Post-Approval Workflow Layer**:
   - Feature 4 provides an audited manual bed-turnover workflow. Starting release
     moves an eligible bed from `occupied` to `vacating`; confirming physical
     departure clears the assignment, changes the bed to `cleaning`, and
     discharges the admission; completing cleaning moves it to `available`.
   - n8n/webhook orchestration, housekeeping automation, hospital matching,
     notifications, transfer departure, and ambulance workflows remain future work
     and are deliberately not invoked by Features 3 or 4.

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
                                ▼
                 [ Pending Internal report_approved Event ]
                                │
                                ▼
      [ Authorized staff: manual bed release when eligible ]
                                │
                                ▼
                  [ Future external orchestration: not invoked ]
```

> **MANDATORY CLINICAL SAFETY CONSTRAINT**:
> AI models ONLY produce unapproved drafts. Under no circumstances does the system auto-approve clinical summaries. In Feature 3, doctor approval records only a pending internal event; downstream automations remain future work.

---

## 2. Technology Stack

- **Frontend**:
  - React 18
  - TypeScript
  - Vite
  - Tailwind CSS
  - React Router v6
  - Axios
  - Lucide React
- **Backend**:
  - Python 3.11+
  - FastAPI
  - SQLAlchemy 2.0 (ORM)
  - Pydantic v2 (Validation & Schemas)
  - Alembic (Database Migrations)
  - PostgreSQL 16 (Primary Relational Database)
  - Uvicorn (ASGI Server)
- **Workflow Automation**:
  - n8n
- **Infrastructure**:
  - Docker Compose
  - Multi-stage Docker build

---

## 3. Monorepo Repository Structure

```text
discharge-orchestration-system/
│
├── frontend/
│   ├── src/
│   │   ├── api/                   # Axios client & health service
│   │   ├── assets/                # Static assets & icons
│   │   ├── components/            # Reusable UI cards, badges, buttons, headers
│   │   ├── features/              # Feature modules (auth, patients, discharge, etc.)
│   │   ├── layouts/               # DashboardLayout, Sidebar, Header
│   │   ├── pages/                 # Route views (Dashboard, Patients, Transfers, etc.)
│   │   ├── hooks/                 # Custom React hooks
│   │   ├── services/              # API wrapper services
│   │   ├── types/                 # TypeScript domain types & interfaces
│   │   ├── utils/                 # Utilities
│   │   ├── App.tsx                # App router setup
│   │   ├── main.tsx               # DOM entrypoint
│   │   └── index.css              # Tailwind base styles
│   ├── .env.example
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/            # Health, Users, Patients, Beds, Discharge, Transfers...
│   │   │   └── dependencies/      # DB session & auth injection
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic Settings
│   │   │   └── security.py        # Token & hashing utilities
│   │   ├── db/
│   │   │   ├── base.py            # SQLAlchemy Base & Model metadata
│   │   │   ├── session.py         # DB Engine & sessionmaker
│   │   │   └── seed.py            # Database seeder with synthetic records
│   │   ├── models/                # SQLAlchemy 2.0 ORM entities
│   │   ├── schemas/               # Pydantic validation & transfer schemas
│   │   ├── repositories/          # Generic BaseRepository & entity repositories
│   │   ├── services/              # Business logic & discharge approval service
│   │   ├── integrations/          # Interfaces for LLM, n8n, Maps, Notifications
│   │   ├── events/                # Internal event persistence; future n8n integration
│   │   └── main.py                # FastAPI app initialization & CORS middleware
│   ├── alembic/                   # Database migrations
│   ├── tests/                     # Pytest suite
│   ├── .env.example
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
│
├── workflows/
│   └── n8n/                       # Post-approval workflow templates
├── data/
│   └── synthetic/                 # Synthetic clinical datasets (patients.json)
├── docs/
│   ├── architecture.md            # System architecture & state machines
│   └── api.md                     # Endpoint specifications
├── docker-compose.yml             # PostgreSQL 16 local stack
├── .gitignore
├── README.md
└── .env.example
```

---

## 4. Local Development Prerequisites

- **Python**: `3.11+`
- **Node.js**: `18+` or `20+` (and `npm`)
- **Docker & Docker Compose**: (for local PostgreSQL instance)

---

## 5. PostgreSQL & Environment Setup

### 1. Copy Environment Configuration
```bash
# Root
cp .env.example .env

# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env
```

### 2. Start PostgreSQL Container
```bash
docker compose up -d postgres
```
PostgreSQL will be running on `localhost:5432` with:
- **Database**: `discharge_orchestration`
- **User**: `postgres`
- **Password**: `postgres`

### AI discharge-report setup

Add a Replicate API token to the ignored `backend/.env` file:

```dotenv
REPLICATE_API_TOKEN=<your-token>
LLM_MODEL=openai/gpt-5.6-luna
```

Install backend requirements and apply migrations before starting the API:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Feature 3 provides an explicit AI-draft action followed by doctor edit, acknowledgement,
and approval. AI output never approves a report. Approval records one internal audit event
and does not itself discharge the patient, release the bed, or start external orchestration.
For an eligible occupied bed, Feature 4 then requires an authorized doctor or ward
administrator to manually start release, confirm departure, and complete cleaning.

---

## 6. Backend Setup & Alembic Migrations

### 1. Create Virtual Environment & Install Dependencies
```bash
cd backend
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run Alembic Migrations & Seed Data
```bash
# Apply migrations to PostgreSQL
alembic upgrade head

# Seed baseline wards, hospitals, capacities, and synthetic patients
python -m app.db.seed
```

### 3. Start Backend Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive API Docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 7. Frontend Setup

### 1. Install Node Dependencies
```bash
cd frontend
npm install
```

### 2. Start Vite Development Server
```bash
npm run dev
```
- Web Application: [http://localhost:5173](http://localhost:5173)

---

## 8. Available Frontend Routes

- `/login` - Clinical Portal Sign-In
- `/dashboard` - Operational Summary & Review Queues
- `/patients` - Inpatient Directory
- `/patients/:patientId` - Patient Chart & Active Admission
- `/patients/:patientId/discharge` - AI Discharge Summary Review & Physician Sign-Off
- `/beds` - Ward Bed Management & Sanitation Status
- `/beds/:bedId` - Bed Detail, Manual Turnover Actions & Transition History
- `/transfers` - Inter-Hospital Transfer Coordination Board
- `/transfers/:transferId` - Transfer Tracking & Ambulance Telemetry
- `/hospitals` - Regional Hospital Directory & Live Specialty Capacities
- `/ambulances` - Ambulance Fleet & Transport Dispatches

Bed-transition confirmation dialogs move focus to the first enabled action, keep
keyboard focus within the dialog, support Escape and backdrop dismissal while
idle, disable every dismissal path during submission, and restore focus to the
action opener (or the stable bed-detail fallback if that opener has unmounted).

---

## 9. Verification & Health Check

### Health Check Endpoint
```bash
curl http://localhost:8000/api/health
```
**Response:**
```json
{
  "status": "ok",
  "service": "discharge-orchestration-api"
}
```

### Run Automated Backend Tests
```bash
cd backend
pytest
```

### Run Frontend Typecheck
```bash
cd frontend
npm run lint
```

### Run Frontend Tests and Production Build
```bash
cd frontend
npm test -- --run
npm run build
```

---

## 10. Current Development Status

- [x] Monorepo structure initialized with clean layer separation.
- [x] PostgreSQL 16 Docker Compose environment.
- [x] 12 Core SQLAlchemy 2.0 ORM models & relationships.
- [x] Alembic migration infrastructure.
- [x] Pydantic v2 schemas for all entities.
- [x] Generic BaseRepository and clinical service layer.
- [x] Mandatory Clinical Safety Doctor Sign-Off protocol enforced.
- [x] Integration placeholder interfaces (LLM, n8n, Maps, Notifications).
- [x] Internal workflow-event persistence (no n8n publisher is invoked by Feature 3).
- [x] React + TypeScript + Vite + Tailwind dashboard with sidebar and live API indicator.
- [x] Synthetic patient dataset infrastructure.
- [x] Feature 4 manual Bed Management APIs and UI: guarded, audited turnover from
  `occupied` to `vacating` to `cleaning` to `available`; report approval alone never
  releases a bed, and no n8n/automation is invoked.
- [ ] *Next Upcoming Feature*: **Transfer departure and external orchestration**
