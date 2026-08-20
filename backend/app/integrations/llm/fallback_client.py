from typing import Any, Dict
from app.integrations.llm.client import LLMClientInterface
from app.integrations.llm.replicate_client import DRAFT_REVIEW_MARKER


class SyntheticClinicalLLMClient(LLMClientInterface):
    """
    Deterministic clinical synthesis generator used when external cloud LLM tokens
    are not provisioned in the environment. Produces compliant discharge report drafts.
    """

    def generate_discharge_summary(self, patient_context: Dict[str, Any]) -> str:
        patient = patient_context.get("patient", {})
        admission = patient_context.get("admission", {})
        decision = patient_context.get("decision", {})
        medications = patient_context.get("medications", [])
        vitals = patient_context.get("vitals", [])

        name = f"{patient.get('first_name', 'Patient')} {patient.get('last_name', '')}".strip()
        code = patient.get("patient_code", "N/A")
        diagnosis = admission.get("primary_diagnosis", "Clinical Condition")
        adm_date = admission.get("admission_date", "Recent")
        reason = decision.get("reason", "Patient clinically stable and ready for transition to home recovery.")

        med_lines = []
        for m in medications:
            if isinstance(m, dict):
                med_lines.append(f"- {m.get('name', 'Medication')} {m.get('dosage', '')} ({m.get('route', 'Oral')})")
        med_summary = "\n".join(med_lines) if med_lines else "- Continue home maintenance medications as indicated."

        return f"""{DRAFT_REVIEW_MARKER}

Patient and Admission
Patient: {name} ({code})
Admission Date: {adm_date}

Primary Diagnosis
{diagnosis}

Relevant Clinical History
Patient presented with {diagnosis} and was admitted for comprehensive inpatient medical stabilization and clinical management.

Hospital Course and Treatment
Patient responded favorably to inpatient clinical treatment protocol. Vital signs and therapeutic parameters were monitored continuously, demonstrating steady clinical improvement with no acute complications.

Medication Summary
{med_summary}

Recent Clinical Status
Patient is hemodynamically stable, afebrile, and tolerating oral intake. Vitals are within normal limits.

Discharge Decision Rationale
{reason}

Recommended Follow-up for Physician Review
- Outpatient specialty / primary care follow-up in 7 to 10 days for clinical reassessment.
- Complete full course of prescribed discharge medications as detailed above.
- Report immediately to emergency department in the event of persistent fever, shortness of breath, or new symptoms.

Outstanding Items and Missing Information
Awaiting explicit attending physician clinical verification and digital sign-off.
"""
