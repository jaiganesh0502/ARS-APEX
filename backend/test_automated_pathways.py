import time
import httpx

base = "https://altaa.duckdns.org/api"

# Reset database for Arun Kumar (PT-1001)
import reset_arun
reset_arun.reset_arun()

print("==================================================")
print("TESTING PATHWAY 1: NORMAL DISCHARGE AUTOMATION")
print("==================================================")

# 1. Doctor login & confirm discharge decision
r_doc = httpx.post(f"{base}/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"}, verify=False)
token_doc = r_doc.json()["access_token"]
h_doc = {"Authorization": f"Bearer {token_doc}"}

r_dec = httpx.post(
    f"{base}/admissions/1/clinical-decision",
    headers=h_doc,
    json={"decision_type": "discharge", "reason": "Patient clinically stable.", "notes": "Completed course."},
    verify=False
)
dec_id = r_dec.json()["id"]
httpx.post(f"{base}/clinical-decisions/{dec_id}/confirm", headers=h_doc, verify=False)

# Upload clinical notes
httpx.post(
    f"{base}/admissions/1/documents",
    headers=h_doc,
    files={"file": ("doctor_progress_notes.pdf", b"%PDF-1.4 pneumonia stable on oral antibiotics.", "application/pdf")},
    data={"document_type": "doctor_handwritten_notes"},
    verify=False
)

# Doctor approves report
r_rep = httpx.get(f"{base}/discharge/admissions/1/report", headers=h_doc, verify=False)
report_id = r_rep.json()["id"]
r_app = httpx.post(
    f"{base}/discharge/reports/{report_id}/approve",
    headers=h_doc,
    json={"acknowledged": True, "clinical_notes": "Reviewed and verified."},
    verify=False
)
print("Doctor Approved Discharge Report! Status:", r_app.status_code)

print("Waiting 5s for background event dispatcher & n8n orchestration...")
time.sleep(5)

# Check invoice & billing clearance
r_rec = httpx.post(f"{base}/auth/login", json={"email": "receptionist@demo.local", "password": "ReceptionDemo123!"}, verify=False)
token_rec = r_rec.json()["access_token"]
h_rec = {"Authorization": f"Bearer {token_rec}"}

r_inv = httpx.get(f"{base}/admissions/1/invoice", headers=h_rec, verify=False)
inv = r_inv.json()
print("Generated Invoice #:", inv.get("invoice_number"), "| Balance: INR", inv.get("balance_amount"), "| Status:", inv.get("payment_status"))

# Receptionist pays invoice
r_pay = httpx.post(
    f"{base}/invoices/{inv['id']}/payments/manual",
    headers=h_rec,
    json={"amount": float(inv["balance_amount"]), "payment_method": "cash", "reference": "REC-DISCHARGE-AUTO-SETTLED"},
    verify=False
)
print("Payment recorded! Status:", r_pay.json().get("payment_status"))

print("Waiting 5s for n8n billing clearance orchestration & package generation...")
time.sleep(5)

# Verify Discharge Package auto-created
r_pkg = httpx.get(f"{base}/admissions/1/discharge-package", headers=h_doc, verify=False)
print("Discharge Package Status Code:", r_pkg.status_code)
if r_pkg.status_code == 200 and r_pkg.json():
    pkg_data = r_pkg.json()
    print("Discharge Package ID:", pkg_data.get("id"), "| Status:", pkg_data.get("status"), "| PDF Ready:", pkg_data.get("pdf_ready"))

print("\n==================================================")
print("TESTING PATHWAY 2: EMERGENCY TRANSFER AUTOMATION")
print("==================================================")

# Reset Arun Kumar to active ADMITTED status again
reset_arun.reset_arun()

# Doctor initiates Emergency Transfer
r_dec_em = httpx.post(
    f"{base}/admissions/1/clinical-decision",
    headers=h_doc,
    json={
        "decision_type": "transfer",
        "urgency": "emergency",
        "specialty": "Cardiology",
        "reason": "Acute Coronary Syndrome requiring immediate Cath Lab",
        "notes": "Emergency ALS transfer requested"
    },
    verify=False
)
em_dec_id = r_dec_em.json()["id"]
r_conf_em = httpx.post(f"{base}/clinical-decisions/{em_dec_id}/confirm", headers=h_doc, verify=False)
print("Emergency Transfer Decision Confirmed! Status:", r_conf_em.status_code)

print("Waiting 5s for background event dispatcher & n8n transfer matching & ambulance dispatch...")
time.sleep(5)

# Check transfer details
r_trans = httpx.get(f"{base}/transfers/admissions/1", headers=h_doc, verify=False)
print("Transfer Record Status:", r_trans.status_code)
if r_trans.status_code == 200:
    trans_data = r_trans.json()
    print("Transfer Status:", trans_data.get("status"))
    print("Urgency:", trans_data.get("urgency"))
    print("Target Hospital:", trans_data.get("receiving_hospital_name"))

# Check ambulance dispatch
r_amb = httpx.get(f"{base}/ambulance/transfers/{trans_data['id']}", headers=h_doc, verify=False)
print("Ambulance Dispatch Status Code:", r_amb.status_code)
if r_amb.status_code == 200:
    amb_data = r_amb.json()
    print("Ambulance Vehicle:", amb_data.get("vehicle_number"), "| Status:", amb_data.get("status"), "| ETA:", amb_data.get("current_eta_minutes"), "mins")
