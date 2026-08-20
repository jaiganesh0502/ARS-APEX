import httpx

base = "https://altaa.duckdns.org/api"

# Doctor Login
r_doc = httpx.post(f"{base}/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"}, verify=False)
h_doc = {"Authorization": f"Bearer {r_doc.json()['access_token']}"}

# Get Patients list
r_pats = httpx.get(f"{base}/patients", headers=h_doc, verify=False)
pats = r_pats.json()["items"]
print("--- Active Patients on Live Server ---")
for p in pats:
    adm = p.get("active_admission") or {}
    bed = adm.get("bed") or {}
    print(f"Patient ID: {p['id']} | Code: {p['patient_code']} | Name: {p['first_name']} {p['last_name']} | Admission Status: {adm.get('status')} | Bed: {bed.get('bed_number')}")

# Check patient login user profile
r_pat = httpx.post(f"{base}/auth/login", json={"email": "patient@demo.local", "password": "PatientDemo123!"}, verify=False)
h_pat = {"Authorization": f"Bearer {r_pat.json()['access_token']}"}
r_prof = httpx.get(f"{base}/patient-portal/profile", headers=h_pat, verify=False)
prof = r_prof.json()
print("\n--- Patient Demo Account currently linked to: ---")
print(f"Patient Code: {prof.get('patient', {}).get('patient_code')} | Name: {prof.get('patient', {}).get('first_name')} {prof.get('patient', {}).get('last_name')}")
