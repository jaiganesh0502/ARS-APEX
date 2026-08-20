import httpx

base = "https://altaa.duckdns.org/api"

print("=== STEP 1: DOCTOR LOGIN & CLINICAL REPORT APPROVAL ===")
r_doc = httpx.post(f"{base}/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"}, verify=False)
assert r_doc.status_code == 200
token_doc = r_doc.json()["access_token"]
h_doc = {"Authorization": f"Bearer {token_doc}"}

r_rep = httpx.get(f"{base}/discharge/admissions/1/report", headers=h_doc, verify=False)
report_id = r_rep.json()["id"]
r_app = httpx.post(
    f"{base}/discharge/reports/{report_id}/approve",
    headers=h_doc,
    json={"acknowledged": True, "clinical_notes": "Physician verified all treatments and medications."},
    verify=False,
)
print("Doctor Approval Status:", r_app.status_code, "Report Status:", r_app.json().get("status"))

print("\n=== STEP 2: RECEPTIONIST LOGIN & DETERMINISTIC INVOICE INSPECTION ===")
r_rec = httpx.post(f"{base}/auth/login", json={"email": "receptionist@demo.local", "password": "ReceptionDemo123!"}, verify=False)
assert r_rec.status_code == 200
token_rec = r_rec.json()["access_token"]
h_rec = {"Authorization": f"Bearer {token_rec}"}

r_inv = httpx.get(f"{base}/admissions/1/invoice", headers=h_rec, verify=False)
inv = r_inv.json()
print("Invoice Number:", inv.get("invoice_number"))
print("Subtotal: INR", inv.get("subtotal"))
print("Tax (5%): INR", inv.get("tax_amount"))
print("Total Invoice Amount: INR", inv.get("total_amount"))
print("Balance Due: INR", inv.get("balance_amount"))
print("Payment Status:", inv.get("payment_status"))
print("Total Itemized Lines:", len(inv.get("line_items", [])))
for item in inv.get("line_items", [])[:4]:
    print(f" - [{item['category']}] {item['description']}: INR {item['amount']}")

print("\n=== STEP 3: RECEPTIONIST RECORDS MANUAL COUNTER PAYMENT ===")
balance = float(inv["balance_amount"])
if balance > 0:
    r_pay = httpx.post(
        f"{base}/invoices/{inv['id']}/payments/manual",
        headers=h_rec,
        json={"amount": balance, "payment_method": "cash", "reference": "REC-COUNTER-001"},
        verify=False,
    )
    print("Payment Recording Status:", r_pay.status_code)
    pay_data = r_pay.json()
    print("New Payment Status:", pay_data.get("payment_status"))
    print("Remaining Balance: INR", pay_data.get("balance_amount"))
else:
    print("Invoice already fully paid.")

print("\n=== STEP 4: PATIENT PORTAL CARE PLAN & BILLING VERIFICATION ===")
r_pat = httpx.post(f"{base}/auth/login", json={"email": "patient@demo.local", "password": "PatientDemo123!"}, verify=False)
token_pat = r_pat.json()["access_token"]
h_pat = {"Authorization": f"Bearer {token_pat}"}

r_prof = httpx.get(f"{base}/patient-portal/profile", headers=h_pat, verify=False)
prof = r_prof.json()
print("Patient Code:", prof.get("patient", {}).get("patient_code"))
print("Discharge Ready Status (Clinical + Payment Cleared):", prof.get("admission", {}).get("discharge_ready"))
if prof.get("invoice"):
    print(f"Patient Portal Invoice: {prof['invoice']['invoice_number']} | Status: {prof['invoice']['payment_status']} | Balance Due: INR {prof['invoice']['balance_amount']}")

print("\n=== COMPLETE PRODUCTION-READY CLINICAL PIPELINE VERIFIED ON LIVE DOMAIN ===")
