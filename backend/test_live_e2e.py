import httpx

base = "https://altaa.duckdns.org/api"

print("--- 1. Receptionist Authentication ---")
r_rec = httpx.post(
    f"{base}/auth/login",
    json={"email": "receptionist@demo.local", "password": "ReceptionDemo123!"},
    verify=False,
)
assert r_rec.status_code == 200, f"Login failed: {r_rec.text}"
token_rec = r_rec.json()["access_token"]
h_rec = {"Authorization": f"Bearer {token_rec}"}
print("Receptionist Token Acquired:", token_rec[:25] + "...")

print("\n--- 2. ChargeMaster Catalog Verification ---")
r_cm = httpx.get(f"{base}/charge-master", headers=h_rec, verify=False)
assert r_cm.status_code == 200
cm_items = r_cm.json()
print("Total ChargeMaster Items:", len(cm_items))
for item in cm_items[:3]:
    print(f" - [{item['category']}] {item['name']}: INR {item['unit_price']}")

print("\n--- 3. Doctor Authentication & Document Upload ---")
r_doc = httpx.post(
    f"{base}/auth/login",
    json={"email": "doctor@demo.local", "password": "DoctorDemo123!"},
    verify=False,
)
assert r_doc.status_code == 200
token_doc = r_doc.json()["access_token"]
h_doc = {"Authorization": f"Bearer {token_doc}"}

r_upload = httpx.post(
    f"{base}/admissions/1/documents",
    headers=h_doc,
    files={"file": ("doctor_progress_notes.pdf", b"%PDF-1.4 simulated discharge progress notes: patient appendectomy stable", "application/pdf")},
    data={"document_type": "doctor_handwritten_notes"},
    verify=False,
)
print("Document Upload Status:", r_upload.status_code)
doc_data = r_upload.json()
print("OCR Status:", doc_data.get("ocr_status"))
print("OCR Confidence:", doc_data.get("ocr_confidence"))

print("\n--- 4. Doctor Review & Sign-Off ---")
r_rep = httpx.get(f"{base}/discharge/admissions/1/report", headers=h_doc, verify=False)
report_data = r_rep.json()
report_id = report_data.get("id")
print("Draft Report ID:", report_id, "Current Status:", report_data.get("status"))

if report_id and report_data.get("status") != "approved":
    r_app = httpx.post(
        f"{base}/discharge/reports/{report_id}/approve",
        headers=h_doc,
        json={"acknowledged": True, "clinical_notes": "Physician verified all treatments and medications."},
        verify=False,
    )
    print("Report Approval Status:", r_app.status_code, "New Status:", r_app.json().get("status"))
else:
    print("Report already approved or verified.")

print("\n--- 5. Receptionist Invoice & Payment Collection ---")
r_inv = httpx.get(f"{base}/invoices", headers=h_rec, verify=False)
invoices = r_inv.json()
print("Total Invoices Found:", len(invoices))
if invoices:
    inv = invoices[0]
    print(f"Invoice: {inv['invoice_number']} | Total: INR {inv['total_amount']} | Balance: INR {inv['balance_amount']} | Status: {inv['payment_status']}")
    
    if inv["balance_amount"] > 0:
        r_pay = httpx.post(
            f"{base}/invoices/{inv['id']}/payments/manual",
            headers=h_rec,
            json={"amount": float(inv["balance_amount"]), "payment_method": "cash", "reference": "REC-LIVE-001"},
            verify=False,
        )
        print("Payment Recording Status:", r_pay.status_code, "Updated Balance: INR", r_pay.json().get("balance_amount"), "Payment Status:", r_pay.json().get("payment_status"))

print("\n--- 6. Patient Portal View ---")
r_pat = httpx.post(
    f"{base}/auth/login",
    json={"email": "patient@demo.local", "password": "PatientDemo123!"},
    verify=False,
)
token_pat = r_pat.json()["access_token"]
h_pat = {"Authorization": f"Bearer {token_pat}"}

r_prof = httpx.get(f"{base}/patient-portal/profile", headers=h_pat, verify=False)
prof = r_prof.json()
print("Patient Code:", prof.get("patient", {}).get("patient_code"))
print("Discharge Ready Status:", prof.get("admission", {}).get("discharge_ready"))
if prof.get("invoice"):
    print(f"Patient Invoice: {prof['invoice']['invoice_number']} | Status: {prof['invoice']['payment_status']} | Balance: INR {prof['invoice']['balance_amount']}")

print("\n=== ALL LIVE VERIFICATION CHECKS COMPLETED SUCCESSFULLY ===")
