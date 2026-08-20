import logging
from app.db.session import SessionLocal
from app.models import (
    Admission,
    AdmissionStatus,
    AmbulanceDispatch,
    Bed,
    BedStatus,
    BillingClearance,
    ChargeMasterItem,
    ClinicalDecision,
    ClinicalDocument,
    DischargePackage,
    DischargeReport,
    Invoice,
    InvoiceLineItem,
    Notification,
    Patient,
    PaymentTransaction,
    Transfer,
    TransferDecision,
    TransferPacket,
    User,
    UserRole,
    WorkflowEvent,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset-all")

def reset_all():
    db = SessionLocal()
    try:
        logger.info("Starting complete clinical database reset...")

        # 1. Clear operational transactions and child entities
        db.query(PaymentTransaction).delete()
        db.query(InvoiceLineItem).delete()
        db.query(Invoice).delete()
        db.query(BillingClearance).delete()
        db.query(DischargePackage).delete()
        db.query(DischargeReport).delete()
        db.query(ClinicalDocument).delete()
        db.query(AmbulanceDispatch).delete()
        db.query(TransferPacket).delete()
        db.query(TransferDecision).delete()
        db.query(Transfer).delete()
        db.query(ClinicalDecision).delete()
        db.query(Notification).delete()
        db.query(WorkflowEvent).delete()
        db.flush()
        logger.info("Cleaned all operational child entities.")

        # 2. Reset all Admissions
        admissions = db.query(Admission).all()
        for adm in admissions:
            adm.status = AdmissionStatus.ADMITTED
            adm.discharge_ready = False
            adm.discharged_at = None
        db.flush()
        logger.info(f"Reset {len(admissions)} admissions to ADMITTED status.")

        # 3. Reset Beds
        beds = db.query(Bed).all()
        for b in beds:
            b.status = BedStatus.AVAILABLE
            b.current_patient_id = None
            b.current_admission_id = None
        db.flush()

        # Assign Bed GM-12 to Arun Kumar (PT-1001)
        arun = db.query(Patient).filter(Patient.patient_code == "PT-1001").first()
        if arun:
            arun_adm = db.query(Admission).filter(Admission.patient_id == arun.id).order_by(Admission.id.asc()).first()
            gm12 = db.query(Bed).filter(Bed.ward == "General Medicine", Bed.bed_number == "GM-12").first()
            if not gm12:
                gm12 = Bed(ward="General Medicine", bed_number="GM-12", status=BedStatus.OCCUPIED)
                db.add(gm12)
                db.flush()
            gm12.status = BedStatus.OCCUPIED
            gm12.current_patient_id = arun.id
            gm12.current_admission_id = arun_adm.id if arun_adm else None
            if arun_adm:
                arun_adm.bed_id = gm12.id
                arun_adm.status = AdmissionStatus.ADMITTED
                arun_adm.primary_diagnosis = "Community Acquired Pneumonia"

            # Link patient user to Arun Kumar
            pat_user = db.query(User).filter(User.email == "patient@demo.local").first()
            if pat_user:
                pat_user.patient_id = arun.id
                pat_user.name = f"{arun.first_name} {arun.last_name}"

        # Seed/Update Receiving Doctor & Receiving Admin
        from app.core.security import hash_password
        rec_doc = db.query(User).filter(User.email == "receiving_doctor@demo.local").first()
        if not rec_doc:
            db.add(User(
                name="Dr. Elena Rostova (Receiving Facility)",
                email="receiving_doctor@demo.local",
                role=UserRole.RECEIVING_DOCTOR,
                password_hash=hash_password("ReceivingDemo123!"),
                is_active=True,
            ))
        else:
            rec_doc.password_hash = hash_password("ReceivingDemo123!")

        rec_adm = db.query(User).filter(User.email == "receiving_admin@demo.local").first()
        if not rec_adm:
            db.add(User(
                name="Vikram Mehta (Receiving Desk)",
                email="receiving_admin@demo.local",
                role=UserRole.RECEIVING_ADMIN,
                password_hash=hash_password("ReceivingAdmin123!"),
                is_active=True,
            ))
        else:
            rec_adm.password_hash = hash_password("ReceivingAdmin123!")

        # Assign other patients to beds if available
        for p in db.query(Patient).filter(Patient.patient_code != "PT-1001").all():
            p_adm = db.query(Admission).filter(Admission.patient_id == p.id).first()
            if p_adm:
                p_adm.status = AdmissionStatus.ADMITTED

        db.commit()
        logger.info("Complete clinical database reset successfully committed!")

    except Exception as e:
        db.rollback()
        logger.error(f"Reset failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    reset_all()
