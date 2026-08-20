import httpx

base = "https://altaa.duckdns.org/api"
r_doc = httpx.post(f"{base}/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"}, verify=False)
h_doc = {"Authorization": f"Bearer {r_doc.json()['access_token']}"}
r = httpx.get(f"{base}/patients", headers=h_doc, verify=False)
for item in r.json()["items"]:
    print(f"[{item['patient_code']}] {item['first_name']} {item['last_name']} | Status: {item['admission_status']} | Diagnosis: {item['primary_diagnosis']} | Ward/Bed: {item['ward']} / {item['bed_number']}")

print("\n--- Checking patient@demo.local Portal View ---")
r_pat = httpx.post(f"{base}/auth/login", json={"email": "patient@demo.local", "password": "PatientDemo123!"}, verify=False)
h_pat = {"Authorization": f"Bearer {r_pat.json()['access_token']}"}
r_prof = httpx.get(f"{base}/patient-portal/profile", headers=h_pat, verify=False)
prof = r_prof.json()
print("Patient Code:", prof.get("patient", {}).get("patient_code"))
print("Name:", prof.get("patient", {}).get("first_name"), prof.get("patient", {}).get("last_name"))
print("Admission Status:", prof.get("admission", {}).get("status"))
print("Ward/Bed:", prof.get("bed", {}).get("ward"), prof.get("bed", {}).get("bed_number"))
print("Discharge Ready:", prof.get("admission", {}).get("discharge_ready"))
print("Invoice:", prof.get("invoice"))
