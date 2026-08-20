from app.db.session import SessionLocal
from app.models import (
    Admission,
    AdmissionStatus,
    AmbulanceDispatch,
    Bed,
    BedStatus,
    BillingClearance,
    ClinicalDecision,
    ClinicalDocument,
    DischargePackage,
    DischargeReport,
    Invoice,
    Notification,
    Patient,
    PaymentTransaction,
    Transfer,
    TransferDecision,
    TransferPacket,
)

def reset_arun():
    db = SessionLocal()
    try:
        patient = db.query(Patient).filter(Patient.patient_code == "PT-1001").first()
        if not patient:
            print("Patient PT-1001 not found!")
            return

        print(f"Found Patient: {patient.first_name} {patient.last_name} (ID: {patient.id})")

        admission = db.query(Admission).filter(Admission.patient_id == patient.id).order_by(Admission.id.desc()).first()
        if not admission:
            print("Admission for PT-1001 not found!")
            return

        # 1. Clean up transfer related entities
        dec_ids = [d.id for d in db.query(ClinicalDecision.id).filter(ClinicalDecision.admission_id == admission.id).all()]
        transfers = db.query(Transfer).filter(
            (Transfer.patient_id == patient.id) | (Transfer.admission_id == admission.id) | (Transfer.clinical_decision_id.in_(dec_ids))
        ).all()
        for t in transfers:
            db.query(AmbulanceDispatch).filter(AmbulanceDispatch.transfer_id == t.id).delete()
            db.query(TransferPacket).filter(TransferPacket.transfer_id == t.id).delete()
            db.query(TransferDecision).filter(TransferDecision.transfer_id == t.id).delete()
            db.delete(t)
        db.flush()

        # 2. Clean up invoices, payments, and billing clearance
        db.query(BillingClearance).filter(BillingClearance.admission_id == admission.id).delete()
        invoices = db.query(Invoice).filter(Invoice.admission_id == admission.id).all()
        for inv in invoices:
            db.query(PaymentTransaction).filter(PaymentTransaction.invoice_id == inv.id).delete()
            db.delete(inv)

        # 3. Clean up packages, reports, documents, decisions, notifications
        db.query(DischargePackage).filter(DischargePackage.admission_id == admission.id).delete()
        db.query(DischargeReport).filter(DischargeReport.admission_id == admission.id).delete()
        db.query(ClinicalDecision).filter(ClinicalDecision.admission_id == admission.id).delete()
        db.query(ClinicalDocument).filter(ClinicalDocument.admission_id == admission.id).delete()
        db.query(Notification).filter(Notification.related_entity_id == admission.id).delete()

        # 4. Get Bed GM-12 in General Medicine
        bed = db.query(Bed).filter(Bed.ward == "General Medicine", Bed.bed_number == "GM-12").first()
        if not bed:
            bed = Bed(ward="General Medicine", bed_number="GM-12", status=BedStatus.OCCUPIED)
            db.add(bed)
            db.flush()

        bed.status = BedStatus.OCCUPIED
        bed.current_patient_id = patient.id
        bed.current_admission_id = admission.id

        # 5. Reset Admission
        admission.status = AdmissionStatus.ADMITTED
        admission.bed_id = bed.id
        admission.discharge_date = None
        admission.discharge_summary = None
        admission.discharge_ready = False
        admission.primary_diagnosis = "Community Acquired Pneumonia"

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
