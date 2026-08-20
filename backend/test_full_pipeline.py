import time
import httpx

base = "https://altaa.duckdns.org/api"

# 1. Login Receptionist
r_rec = httpx.post(f"{base}/auth/login", json={"email": "receptionist@demo.local", "password": "ReceptionDemo123!"}, verify=False)
token_rec = r_rec.json()["access_token"]
h_rec = {"Authorization": f"Bearer {token_rec}"}

# 2. Receptionist registers a new unique patient
pat_code = f"PT-NEW-{int(time.time())}"
r_pat = httpx.post(
    f"{base}/patients",
    headers=h_rec,
    json={"first_name": "Aarav", "last_name": "Mehta", "patient_code": pat_code, "date_of_birth": "1988-04-14", "gender": "Male"},
    verify=False,
)
print("Registered Patient:", r_pat.status_code, r_pat.json().get("id"), r_pat.json().get("patient_code"))
pat_id = r_pat.json()["id"]

# 3. Login Doctor
r_doc = httpx.post(f"{base}/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"}, verify=False)
token_doc = r_doc.json()["access_token"]
h_doc = {"Authorization": f"Bearer {token_doc}"}

# 4. Doctor uploads clinical document for Admission 1
r_doc_upload = httpx.post(
    f"{base}/admissions/1/documents",
    headers=h_doc,
    files={"file": ("clinical_progress_chart.txt", b"CLINICAL PROGRESS NOTES: Patient status post appendectomy. Stable on oral liquids and antibiotics.", "text/plain")},
    data={"document_type": "doctor_handwritten_notes"},
    verify=False,
)
print("Doctor Upload & OCR:", r_doc_upload.status_code, r_doc_upload.json().get("ocr_status"), "Confidence:", r_doc_upload.json().get("ocr_confidence"))

# Check structured data
print("Structured Data Meds:", r_doc_upload.json().get("structured_data", {}).get("medications"))
print("Structured Data Treatments:", r_doc_upload.json().get("structured_data", {}).get("treatments_performed"))
