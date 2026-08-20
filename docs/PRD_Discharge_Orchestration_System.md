# Product Requirements Document (PRD)
## AI-Powered Discharge Orchestration System

**Version:** 1.0
**Track:** MedTech / HealthTech
**Prepared for:** SIH 2026 Submission

---

## 1. Problem Statement

Hospital discharge and inter-facility patient transfer processes are handled manually today — discharge summaries are compiled by hand from scattered EHR data, bed release is communicated informally (calls, notes), and transfers to other facilities involve manual phone-based coordination for bed availability and ambulance dispatch. This causes:

- Delayed bed turnover, reducing hospital capacity
- Documentation errors during handoff (medication, diagnosis, treatment history)
- Time-critical delays in inter-hospital transfers for critical patients
- No single system tracking the patient from "discharge decision" to "arrival at next facility"

## 2. Objective (future product vision)

Build a future end-to-end pipeline that takes a discharge/transfer decision from a doctor and may automate approved downstream steps such as report generation, next-facility matching, and ambulance dispatch. This is not current Feature 4 behavior: bed release remains a manual, authorized, internal FastAPI workflow.

## 3. Novelty / Differentiation

| Existing Solutions | Gap | This System |
|---|---|---|
| NICE-HMS, Lifemaan, DischargeX, Aduvera | Generate discharge summary PDF, stop there | Report generation is step 1 of a full pipeline, not the end product |
| Medbed, RapidRescueIndia, state bed dashboards | Show bed/hospital availability, no case file attached | Referral match comes bundled with the actual transfer report |
| Manual ambulance coordination | Phone-based, no ETA visibility | Automated dispatch trigger + live ETA |

**Core novelty (future vision):** a single continuous pipeline — *discharge decision → AI-generated report → bed release → next-facility match → transfer packet sent → ambulance dispatched* — where no existing product chains all these steps together. Current Feature 4 does not invoke its external-orchestration portions.

## 4. Users

- **Attending Doctor** — approves discharge/transfer, signs off on report
- **Ward Admin / Nursing Staff** — sees bed status update in real time
- **Receiving Hospital Staff** — receives transfer packet, confirms bed
- **Patient/Family** (secondary) — receives plain-language discharge summary

## 5. Core Modules

### 5.1 Discharge Report Generation
- Pulls patient data (diagnosis, medications, vitals, treatment course) from EHR (mocked for MVP)
- LLM drafts a structured discharge summary from a clinical template
- Doctor reviews, edits, digitally signs off — mandatory human-in-loop, no auto-finalization
- Outputs signed PDF + structured JSON for downstream modules

### 5.2 Bed Release Trigger
- Current Feature 4 requires an authorized doctor or ward administrator to explicitly start release after report approval; approval alone does not move the bed.
- The only normal path is `occupied -> vacating -> cleaning -> available`.
- Confirming physical departure clears the assignment and discharges the matching admission; completing cleaning makes the bed available.
- There is no current n8n trigger, webhook, live push, or unrestricted bed-status PATCH route.

### 5.3 Next-Facility Booking (transfer cases only)
- Matching engine ranks partner hospitals by specialty match, live bed capacity, and distance
- Doctor selects a hospital from top-ranked suggestions
- Transfer packet (the signed report) is sent to the receiving hospital's queue
- Receiving hospital confirms → bed reserved

### 5.4 Ambulance Dispatch
- Triggered automatically once a transfer hospital is confirmed
- ETA calculated via Maps API (distance + live traffic)
- Status tracked: requested → en route → arrived (simulated dispatch for MVP)

## 6. System Architecture

**Orchestration layer — n8n (future planning)**
- May own separately approved post-approval automation as visual workflows
- Is not triggered by the current `report_approved` event
- Does not control Feature 4 bed release; current bed turnover is a manual,
  authorized FastAPI workflow
- Future candidates include hospital matching, ambulance triggers, and notifications

**Application layer**
- Frontend: React + Tailwind — doctor/admin dashboard
- Backend: FastAPI — auth, EHR data handling, LLM report generation, serves UI,
  and owns the internal manual Feature 4 bed workflow
- Database: PostgreSQL — patients, beds, hospitals, transfers

**Ownership split**
- FastAPI: auth, EHR data, report drafting (LLM), UI-facing endpoints, and manual
  bed turnover (`occupied -> vacating -> cleaning -> available`)
- n8n: future-only external orchestration; it is not invoked by current approval
  or bed-transition events

## 7. AWS Deployment

| Component | Service |
|---|---|
| Frontend | S3 + CloudFront (or Amplify) |
| Backend (FastAPI) | ECS/Fargate |
| Database | RDS (PostgreSQL) |
| n8n | Self-hosted on EC2 + EBS (persistent storage needed) |
| Secrets (LLM/Maps API keys) | AWS Secrets Manager |

## 8. MVP Scope

**In scope:**
1. Synthetic patient dataset (5–10 realistic dummy records)
2. Clinician-started AI-assisted discharge draft generation + doctor review/approve screen
3. Live bed status dashboard, refreshed after authorized manual bed actions (not on approval alone)
4. Mock hospital network (3–4 partner hospitals) for referral matching demo
5. Ambulance ETA simulation via Maps API

**Out of scope (future work):**
- Real EHR system integration
- Live ambulance company API integration
- Full multi-hospital authentication/onboarding system
- Regulatory/compliance certification (HIPAA/DPDP-equivalent)

## 9. Risks

- **Clinical accuracy risk:** LLM-drafted reports must never auto-finalize without doctor sign-off
- **Data availability:** no real hospital data access expected during hackathon — mitigated with synthetic MIMIC-IV-style datasets
- **n8n on EC2 persistence:** workflows and credentials must persist across restarts — needs EBS-backed volume, not ephemeral storage

## 10. Success Metrics (for demo/pitch)

- End-to-end time from "doctor approves discharge" to "ambulance dispatched + bed confirmed at next facility" — target under 2 minutes in simulated demo
- Reduction in manual steps: from ~5 disconnected actions (call bed desk, call ambulance, call next hospital, fax report, update records) to 1 approval click
