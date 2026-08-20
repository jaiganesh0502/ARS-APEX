from app.db.session import SessionLocal
from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    ClinicalDecision,
    ClinicalDecisionStatus,
    ClinicalDocument,
    DischargeReport,
    Invoice,
    Patient,
    PaymentTransaction,
    TransferRequest,
    WorkflowEvent,
)

def reset_arun():
    db = SessionLocal()
    try:
        patient = db.query(Patient).filter(Patient.patient_code == "PT-1001").first()
        if not patient:
            print("Patient PT-1001 not found!")
            return

        print(f"Found Patient: {patient.first_name} {patient.last_name} (ID: {patient.id})")

        # 1. Clear any active transfer requests
        transfers = db.query(TransferRequest).filter(TransferRequest.patient_id == patient.id).all()
        for t in transfers:
            db.delete(t)

        # 2. Get Bed GM-12 in General Medicine
        bed = db.query(Bed).filter(Bed.ward == "General Medicine", Bed.bed_number == "GM-12").first()
        if not bed:
            bed = Bed(ward="General Medicine", bed_number="GM-12", status=BedStatus.OCCUPIED)
            db.add(bed)
            db.flush()

        bed.status = BedStatus.OCCUPIED
        bed.current_patient_id = patient.id

        # 3. Find or reset Admission
        admission = db.query(Admission).filter(Admission.patient_id == patient.id).order_by(Admission.id.desc()).first()
        if admission:
            admission.status = AdmissionStatus.ADMITTED
            admission.bed_id = bed.id
            admission.discharge_date = None
            admission.discharge_summary = None
            admission.discharge_ready = False
            admission.primary_diagnosis = "Community Acquired Pneumonia"
            bed.current_admission_id = admission.id
            print(f"Reset Admission ID: {admission.id} to ADMITTED in Bed GM-12")

            # 4. Clean up any previous invoices / payments for fresh test
            invoices = db.query(Invoice).filter(Invoice.admission_id == admission.id).all()
            for inv in invoices:
                # delete payment transactions first
                db.query(PaymentTransaction).filter(PaymentTransaction.invoice_id == inv.id).delete()
                db.delete(inv)

            # 5. Clean up old discharge reports and decisions if any
            db.query(DischargeReport).filter(DischargeReport.admission_id == admission.id).delete()
            db.query(ClinicalDecision).filter(ClinicalDecision.admission_id == admission.id).delete()
            db.query(ClinicalDocument).filter(ClinicalDocument.admission_id == admission.id).delete()

        db.commit()
        print("Successfully reset Arun Kumar (PT-1001) to active ADMITTED status in Bed GM-12!")
    except Exception as e:
        db.rollback()
        print(f"Error resetting Arun Kumar: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    reset_arun()
