import httpx

base = "https://altaa.duckdns.org/api"

# 1. Reset Arun Kumar
import reset_arun
reset_arun.reset_arun()

print("--- 1. Doctor Confirms Discharge Decision ---")
r_doc = httpx.post(f"{base}/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"}, verify=False)
token_doc = r_doc.json()["access_token"]
h_doc = {"Authorization": f"Bearer {token_doc}"}

# Doctor creates & confirms decision
r_dec = httpx.post(
    f"{base}/clinical-decisions/1",
    headers=h_doc,
    json={"decision_type": "discharge", "reason": "Patient clinically stable.", "notes": "Completed course."},
    verify=False
)
dec_id = r_dec.json()["id"]
r_conf = httpx.post(f"{base}/clinical-decisions/{dec_id}/confirm", headers=h_doc, verify=False)
print("Decision Confirmed Status:", r_conf.status_code)

# Doctor uploads source notes
r_up = httpx.post(
    f"{base}/admissions/1/documents",
    headers=h_doc,
    files={"file": ("doctor_progress_notes.pdf", b"%PDF-1.4 patient pneumonia stable on oral antibiotics.", "application/pdf")},
    data={"document_type": "doctor_handwritten_notes"},
    verify=False
)
print("Upload status:", r_up.status_code, r_up.json().get("ocr_status"))

# Doctor approves report
r_rep = httpx.get(f"{base}/discharge/admissions/1/report", headers=h_doc, verify=False)
report_id = r_rep.json()["id"]
r_app = httpx.post(
    f"{base}/discharge/reports/{report_id}/approve",
    headers=h_doc,
    json={"acknowledged": True, "clinical_notes": "Reviewed and verified."},
    verify=False
)
print("Doctor Report Approval Status:", r_app.status_code)

print("\n--- 2. Inspect Billing Clearance & Invoice ---")
r_rec = httpx.post(f"{base}/auth/login", json={"email": "receptionist@demo.local", "password": "ReceptionDemo123!"}, verify=False)
token_rec = r_rec.json()["access_token"]
h_rec = {"Authorization": f"Bearer {token_rec}"}

r_inv = httpx.get(f"{base}/admissions/1/invoice", headers=h_rec, verify=False)
inv = r_inv.json()
print("Invoice #:", inv.get("invoice_number"))
print("Invoice Balance Due: INR", inv.get("balance_amount"))
print("Invoice Payment Status:", inv.get("payment_status"))

# Check patient profile for billing clearance
r_pat = httpx.post(f"{base}/auth/login", json={"email": "patient@demo.local", "password": "PatientDemo123!"}, verify=False)
token_pat = r_pat.json()["access_token"]
h_pat = {"Authorization": f"Bearer {token_pat}"}
r_prof = httpx.get(f"{base}/patient-portal/profile", headers=h_pat, verify=False)
prof = r_prof.json()
print("Discharge Ready before payment (Should be False):", prof.get("admission", {}).get("discharge_ready"))

print("\n--- 3. Check Medical Superintendent Notifications ---")
r_ms = httpx.post(f"{base}/auth/login", json={"email": "superintendent@demo.local", "password": "SuperDemo123!"}, verify=False)
token_ms = r_ms.json()["access_token"]
h_ms = {"Authorization": f"Bearer {token_ms}"}
r_notif = httpx.get(f"{base}/notifications", headers=h_ms, verify=False)
notifs = r_notif.json()["items"]
print(f"Total MS Notifications: {len(notifs)}")
for n in notifs:
    print(f" - [{n['subject']}]: {n['message']}")

print("\n--- 4. Receptionist Settles Payment ---")
r_pay = httpx.post(
    f"{base}/invoices/{inv['id']}/payments/manual",
    headers=h_rec,
    json={"amount": float(inv["balance_amount"]), "payment_method": "cash", "reference": "REC-LIVE-CLEARED"},
    verify=False
)
print("Payment Status:", r_pay.status_code, r_pay.json().get("payment_status"))

# Check MS Notifications again after payment
r_notif2 = httpx.get(f"{base}/notifications", headers=h_ms, verify=False)
notifs2 = r_notif2.json()["items"]
print(f"\nTotal MS Notifications after Payment: {len(notifs2)}")
for n in notifs2:
    print(f" - [{n['subject']}]: {n['message']}")

# Check discharge ready
r_prof2 = httpx.get(f"{base}/patient-portal/profile", headers=h_pat, verify=False)
print("Discharge Ready after payment (Should be True):", r_prof2.json().get("admission", {}).get("discharge_ready"))
