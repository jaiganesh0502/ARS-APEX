from datetime import datetime, timezone
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admission import Admission
from app.models.bed import Bed
from app.models.clinical_decision import ClinicalDecision, ClinicalDecisionStatus, TransferUrgency
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.models.hospital import Hospital
from app.models.medical_record import MedicalRecord
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.transfer import Transfer, TransferStatus
from app.models.transfer_packet import TransferPacket, TransferPacketStatus
from app.models.user import User
from app.models.vital import Vital
from app.models.workflow_event import WorkflowEvent

logger = logging.getLogger(__name__)


class TransferPacketService:
    """
    Assembles, snapshots, delivers, and tracks structured clinical transfer packets.
    """

    def __init__(self, db: Session):
        self.db = db

    def _get_transfer(self, transfer_id: int) -> Transfer:
        transfer = self.db.get(Transfer, transfer_id)
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found",
            )
        return transfer

    def prepare_packet(self, transfer_id: int) -> TransferPacket:
        """
        Assemble and persist a clinical transfer packet for the selected receiving facility.
        Guarantees idempotency and prevents duplicate packet creation.
        """
        transfer = self._get_transfer(transfer_id)

        if transfer.receiving_hospital_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot prepare transfer packet before a receiving hospital has been selected.",
            )

        # Return existing packet if already assembled
        existing_packet = (
            self.db.query(TransferPacket)
            .filter(TransferPacket.transfer_id == transfer.id)
            .order_by(TransferPacket.id.desc())
            .first()
        )
        if existing_packet:
            logger.info("Transfer packet %s already exists for transfer %s", existing_packet.id, transfer.id)
            return existing_packet

        # Collect clinical records and relations
        patient = self.db.get(Patient, transfer.patient_id)
        admission = self.db.get(Admission, transfer.admission_id)
        if not patient or not admission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient or admission records missing for transfer.",
            )

        bed = self.db.get(Bed, admission.bed_id) if admission.bed_id else None
        sending_hospital = self.db.get(Hospital, transfer.sending_hospital_id)
        receiving_hospital = self.db.get(Hospital, transfer.receiving_hospital_id)
        attending_doctor = self.db.get(User, admission.attending_doctor_id)

        decision = (
            self.db.query(ClinicalDecision)
            .filter(
                ClinicalDecision.admission_id == admission.id,
                ClinicalDecision.status == ClinicalDecisionStatus.CONFIRMED,
            )
            .order_by(ClinicalDecision.decided_at.desc(), ClinicalDecision.id.desc())
            .first()
        )

        medical_records = (
            self.db.query(MedicalRecord)
            .filter(MedicalRecord.admission_id == admission.id)
            .order_by(MedicalRecord.created_at.desc())
            .all()
        )
        treatment_course = "\n\n".join([m.treatment_course for m in medical_records if m.treatment_course]) or "Routine inpatient care."
        clinical_notes = "\n\n".join([m.notes for m in medical_records if m.notes]) or (decision.notes if decision else None)

        medications = (
            self.db.query(Medication)
            .filter(Medication.admission_id == admission.id)
            .order_by(Medication.start_date.desc())
            .all()
        )

        vitals = (
            self.db.query(Vital)
            .filter(Vital.admission_id == admission.id)
            .order_by(Vital.recorded_at.desc())
            .limit(5)
            .all()
        )

        approved_report = (
            self.db.query(DischargeReport)
            .filter(
                DischargeReport.admission_id == admission.id,
                DischargeReport.status == DischargeReportStatus.APPROVED,
            )
            .first()
        )

        urgency_str = "emergency" if transfer.emergency or (decision and decision.transfer_urgency == TransferUrgency.EMERGENCY) else "standard"

        packet_content = {
            "transfer_id": transfer.id,
            "patient_summary": {
                "patient_id": patient.id,
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "patient_code": patient.patient_code,
                "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
                "gender": patient.gender,
                "blood_group": patient.blood_group,
                "phone": patient.phone,
                "emergency_contact": patient.emergency_contact,
            },
            "admission_summary": {
                "admission_id": admission.id,
                "admission_date": admission.admission_date.isoformat(),
                "ward": bed.ward if bed else None,
                "bed_number": bed.bed_number if bed else None,
                "status": admission.status.value,
            },
            "primary_diagnosis": admission.primary_diagnosis,
            "transfer_reason": decision.reason if decision else "Tertiary specialized care required.",
            "required_specialty": transfer.required_specialty,
            "urgency": urgency_str,
            "treatment_course": treatment_course,
            "current_medications": [
                {
                    "medication_name": m.medication_name,
                    "dosage": m.dosage,
                    "frequency": m.frequency,
                    "route": m.route,
                    "start_date": m.start_date.isoformat() if m.start_date else None,
                    "end_date": m.end_date.isoformat() if m.end_date else None,
                }
                for m in medications
            ],
            "recent_vitals": [
                {
                    "temperature": v.temperature,
                    "heart_rate": v.heart_rate,
                    "blood_pressure": f"{v.blood_pressure_systolic}/{v.blood_pressure_diastolic} mmHg",
                    "oxygen_saturation": v.oxygen_saturation,
                    "recorded_at": v.recorded_at.isoformat(),
                }
                for v in vitals
            ],
            "clinical_notes": clinical_notes,
            "approved_discharge_summary": approved_report.edited_content or approved_report.generated_content if approved_report else None,
            "sending_hospital": {
                "hospital_id": sending_hospital.id if sending_hospital else 1,
                "hospital_name": sending_hospital.name if sending_hospital else "Host Medical Center",
                "contact_number": sending_hospital.contact_number if sending_hospital else "+1-415-555-0100",
            },
            "sending_doctor": {
                "doctor_id": attending_doctor.id if attending_doctor else None,
                "name": attending_doctor.name if attending_doctor else "Attending Physician",
                "email": attending_doctor.email if attending_doctor else None,
            },
            "receiving_hospital": {
                "hospital_id": receiving_hospital.id if receiving_hospital else transfer.receiving_hospital_id,
                "hospital_name": receiving_hospital.name if receiving_hospital else "Destination Facility",
                "contact_number": receiving_hospital.contact_number if receiving_hospital else "+1-415-555-0200",
            },
        }

        packet = TransferPacket(
            transfer_id=transfer.id,
            patient_id=patient.id,
            admission_id=admission.id,
            packet_content=packet_content,
            status=TransferPacketStatus.PREPARED,
            prepared_at=datetime.now(timezone.utc),
        )
        self.db.add(packet)
        self.db.commit()
        self.db.refresh(packet)

        logger.info("Prepared transfer packet %s for transfer %s", packet.id, transfer.id)
        return packet

    def get_packet(self, transfer_id: int, mark_viewed: bool = False) -> TransferPacket:
        """
        Fetch transfer packet. If mark_viewed=True and status is SENT, transitions to VIEWED.
        """
        packet = (
            self.db.query(TransferPacket)
            .filter(TransferPacket.transfer_id == transfer_id)
            .order_by(TransferPacket.id.desc())
            .first()
        )
        if not packet:
            # Auto-prepare if transfer has receiving hospital
            transfer = self._get_transfer(transfer_id)
            if transfer.receiving_hospital_id:
                packet = self.prepare_packet(transfer_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Transfer packet not found and no receiving hospital selected.",
                )

        if mark_viewed and packet.status == TransferPacketStatus.SENT:
            packet.status = TransferPacketStatus.VIEWED
            packet.viewed_at = datetime.now(timezone.utc)

            event = WorkflowEvent(
                event_type="transfer_packet_viewed",
                entity_type="transfer",
                entity_id=transfer_id,
                status="pending",
                trusted_provenance=True,
                payload={
                    "transfer_id": transfer_id,
                    "packet_id": packet.id,
                    "patient_id": packet.patient_id,
                    "viewed_at": packet.viewed_at.isoformat(),
                },
            )
            self.db.add(event)
            self.db.commit()
            self.db.refresh(packet)

        return packet

    def send_packet(self, transfer_id: int, sender_user: Optional[User] = None) -> TransferPacket:
        """
        Simulate secure delivery into the destination hospital application queue.
        """
        packet = self.get_packet(transfer_id)

        if packet.status in (TransferPacketStatus.SENT, TransferPacketStatus.VIEWED):
            logger.info("Packet %s already sent for transfer %s", packet.id, transfer_id)
            return packet

        packet.status = TransferPacketStatus.SENT
        packet.sent_at = datetime.now(timezone.utc)

        transfer = self._get_transfer(transfer_id)

        event = WorkflowEvent(
            event_type="transfer_packet_sent",
            entity_type="transfer",
            entity_id=transfer_id,
            status="pending",
            trusted_provenance=True,
            payload={
                "transfer_id": transfer_id,
                "packet_id": packet.id,
                "patient_id": packet.patient_id,
                "admission_id": packet.admission_id,
                "sending_hospital_id": transfer.sending_hospital_id,
                "receiving_hospital_id": transfer.receiving_hospital_id,
                "sent_by": sender_user.id if sender_user else None,
                "sent_at": packet.sent_at.isoformat(),
            },
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(packet)

        logger.info("Sent transfer packet %s for transfer %s", packet.id, transfer_id)
        return packet
