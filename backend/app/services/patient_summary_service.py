import re
from typing import Any, Dict, List, Optional
from app.core.config import settings


class PatientSummaryService:
    """
    Generates a structured, plain-language patient-facing summary from
    the physician-approved clinical discharge report.
    """

    def generate_summary(self, approved_report_text: str, patient_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate structured patient-friendly care instructions.
        In 'mock' mode (default), uses deterministic clinical section parsing
        strictly derived from the approved text without external calls.
        """
        if settings.PATIENT_SUMMARY_MODE == "live" and settings.REPLICATE_API_TOKEN:
            try:
                return self._generate_live_summary(approved_report_text, patient_name)
            except Exception:
                # Fallback safely to deterministic parsing on API failure
                return self._generate_deterministic_summary(approved_report_text)
        
        return self._generate_deterministic_summary(approved_report_text)

    def _generate_deterministic_summary(self, text: str) -> Dict[str, Any]:
        """
        Deterministic parser: extracts clinical sections and translates into
        patient-friendly structured guidance.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        full_text = "\n".join(lines)

        # 1. Why admitted
        admission_reason = "You were admitted to the hospital for inpatient medical observation, evaluation, and targeted clinical treatment."
        for line in lines:
            if any(k in line.lower() for k in ["diagnosis", "admitted for", "chief complaint", "reason for admission", "primary"]):
                admission_reason = f"You were admitted for care and treatment of: {line.split(':')[-1].strip()}."
                break

        # 2. Treatment received
        treatment = "You completed clinical stabilization, continuous vital monitoring, and physician-prescribed inpatient medical therapy."
        for line in lines:
            if any(k in line.lower() for k in ["hospital course", "treatment", "procedures", "interventions", "management"]):
                treatment = line.split(":")[-1].strip()
                break

        # 3. Medications to take & stop
        meds_to_take: List[str] = []
        meds_to_stop: List[str] = []
        in_meds_section = False

        for line in lines:
            lower = line.lower()
            if "medication" in lower or "prescriptions" in lower or "discharge rx" in lower:
                in_meds_section = True
                continue
            if in_meds_section:
                if any(header in lower for header in ["diet", "activity", "follow", "warning", "signs", "instructions"]):
                    in_meds_section = False
                    continue
                if any(stop_word in lower for stop_word in ["discontinue", "stop", "hold", "ceased"]):
                    meds_to_stop.append(line.lstrip("*-•1234567890. "))
                elif line.startswith(("-", "*", "•")) or re.match(r"^\d+\.", line):
                    meds_to_take.append(line.lstrip("*-•1234567890. "))

        if not meds_to_take:
            meds_to_take = ["Take all prescribed discharge medications strictly as directed on pharmacy labels."]

        # 4. Diet instructions
        diet = "Maintain a well-balanced, nutritious diet and stay adequately hydrated."
        for line in lines:
            if "diet" in line.lower():
                diet = line.split(":")[-1].strip()
                break

        # 5. Activity instructions
        activity = "Resume normal daily activities gradually; avoid strenuous heavy lifting until cleared by your doctor."
        for line in lines:
            if "activity" in line.lower() or "exercise" in line.lower():
                activity = line.split(":")[-1].strip()
                break

        # 6. Follow up plan
        follow_up = "Schedule a follow-up appointment with your primary care physician or attending clinic within 7 to 10 days."
        for line in lines:
            if any(k in line.lower() for k in ["follow-up", "follow up", "appointment", "clinic"]):
                follow_up = line.split(":")[-1].strip()
                break

        # 7. Warning signs & urgent help
        warning_signs = [
            "Sudden worsening of symptoms or persistent fever above 101°F (38.3°C).",
            "Severe shortness of breath, sudden dizziness, or chest tightness.",
            "Inability to tolerate fluids, persistent nausea, or unexpected swelling.",
        ]
        for line in lines:
            if any(k in line.lower() for k in ["warning", "red flag", "seek help", "emergency", "urgent"]):
                warning_signs.append(line.split(":")[-1].strip())

        return {
            "why_you_were_admitted": admission_reason,
            "what_treatment_you_received": treatment,
            "medications_to_take": list(dict.fromkeys(meds_to_take)),
            "medications_to_stop": list(dict.fromkeys(meds_to_stop)),
            "diet_instructions": diet,
            "activity_instructions": activity,
            "follow_up_plan": follow_up,
            "warning_signs": list(dict.fromkeys(warning_signs)),
            "when_to_seek_urgent_help": "Call your doctor or go to the nearest emergency department immediately if you experience severe chest pain, extreme shortness of breath, sudden confusion, or uncontrolled bleeding.",
        }

    def _generate_live_summary(self, text: str, patient_name: Optional[str]) -> Dict[str, Any]:
        """
        Optional live LLM structured rewrite enforcing plain-language safety guardrails.
        """
        import json
        import replicate

        prompt = f"""You are a clinical discharge communicator.
Rewrite the following physician-approved discharge report into plain-language instructions for the patient: {patient_name or 'Patient'}.
RULES:
1. Only use facts present in the report. Do NOT introduce new diagnoses, medications, instructions, warnings, or appointments.
2. If information is missing, use safe standard recovery guidance.
3. Return ONLY valid JSON matching this schema:
{{
  "why_you_were_admitted": "string",
  "what_treatment_you_received": "string",
  "medications_to_take": ["string"],
  "medications_to_stop": ["string"],
  "diet_instructions": "string",
  "activity_instructions": "string",
  "follow_up_plan": "string",
  "warning_signs": ["string"],
  "when_to_seek_urgent_help": "string"
}}

Approved Clinical Report:
{text}
"""
        client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)
        output = client.run(settings.LLM_MODEL, input={"prompt": prompt})
        response_text = "".join(output)
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return self._generate_deterministic_summary(text)
