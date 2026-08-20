import httpx

base = "https://altaa.duckdns.org/api"
r_doc = httpx.post(f"{base}/auth/login", json={"email": "doctor@demo.local", "password": "DoctorDemo123!"}, verify=False)
h_doc = {"Authorization": f"Bearer {r_doc.json()['access_token']}"}

for pid in [1, 2, 3]:
    r = httpx.get(f"{base}/patients/{pid}", headers=h_doc, verify=False)
    p = r.json()
    pat = p.get("patient", p)
    adms = p.get("admissions", [])
    print(f"Patient: {pat.get('first_name')} {pat.get('last_name')} ({pat.get('patient_code')}) | Admissions Count: {len(adms)}")
    for a in adms:
        bed_num = a.get("bed", {}).get("bed_number") if a.get("bed") else "None"
        print(f"  - Admission ID: {a['id']} | Status: {a['status']} | Diagnosis: {a['primary_diagnosis']} | Bed: {bed_num}")

