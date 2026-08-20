from datetime import date
from decimal import Decimal
import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    Admission,
    AdmissionStatus,
    ClinicalDecision,
    ClinicalDecisionStatus,
    ClinicalDecisionType,
    ClinicalDocument,
    DischargeReport,
    DischargeReportStatus,
    DocumentStatus,
    Patient,
    User,
    UserRole,
)
from app.services.clinical_document_service import ClinicalDocumentService
from app.services.ocr.ocr_provider import DefaultClinicalOCRProvider, OCRExtractionResult


@pytest.fixture
def mock_ocr_engine(monkeypatch):
    class CustomOCR(DefaultClinicalOCRProvider):
        def extract_text(self, file_bytes: bytes, mime_type: str, file_name: str = "") -> OCRExtractionResult:
            return OCRExtractionResult(
                raw_text="CONFIRMED CLINICAL PROGRESS NOTES: Patient recovering post appendectomy. Stable.",
                confidence=96.8,
                metadata={"test_mode": True},
            )

    return CustomOCR()


def test_clinical_document_upload_and_auto_ocr(db_session, mock_ocr_engine):
    # Setup patient, doctor, admission
    patient = Patient(first_name="Anil", last_name="Kumar", patient_code="PT-DOC-1", date_of_birth=date(1985, 5, 12), gender="Male")
    db_session.add(patient)
    db_session.flush()

    doctor = User(name="Dr. Tester", email="doctest@test.org", role=UserRole.DOCTOR, is_active=True)
    db_session.add(doctor)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        attending_doctor_id=doctor.id,
        primary_diagnosis="Acute Appendicitis",
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(admission)
    db_session.flush()

    decision = ClinicalDecision(
        admission_id=admission.id,
        patient_id=patient.id,
        decided_by=doctor.id,
        decision_type=ClinicalDecisionType.DISCHARGE,
        status=ClinicalDecisionStatus.CONFIRMED,
        reason="Patient afebrile and tolerating oral fluids.",
    )
    db_session.add(decision)
    db_session.commit()

    # Test Document Service Upload & Auto OCR
    svc = ClinicalDocumentService(db_session, ocr_provider=mock_ocr_engine)
    doc = svc.upload_document(
        admission_id=admission.id,
        uploader=doctor,
        file_name="handwritten_progress_notes.pdf",
        file_bytes=b"%PDF-1.4 simulated pdf document bytes for testing",
        mime_type="application/pdf",
        document_type="doctor_handwritten_notes",
    )

    assert doc.id is not None
    assert doc.ocr_status == DocumentStatus.EXTRACTION_COMPLETED
    assert doc.ocr_confidence == 96.8
    assert "CONFIRMED CLINICAL PROGRESS NOTES" in doc.ocr_raw_text
    assert doc.structured_data is not None
    assert "treatments_performed" in doc.structured_data
    assert "medications" in doc.structured_data

    # Verify auto draft generation
    report = db_session.query(DischargeReport).filter(DischargeReport.admission_id == admission.id).first()
    assert report is not None
    assert report.status == DischargeReportStatus.GENERATED
    assert "DRAFT — REQUIRES PHYSICIAN REVIEW AND SIGN-OFF" in report.generated_content
    assert "handwritten_progress_notes.pdf" in report.generated_content


def test_ocr_failure_handling_and_retry(db_session):
    class FailingOCR(DefaultClinicalOCRProvider):
        def extract_text(self, file_bytes: bytes, mime_type: str, file_name: str = "") -> OCRExtractionResult:
            raise RuntimeError("OCR scanner optical sensor timeout")

    patient = Patient(first_name="Sunita", last_name="Devi", patient_code="PT-DOC-2", date_of_birth=date(1990, 1, 1), gender="Female")
    db_session.add(patient)
    db_session.flush()

    doctor = User(name="Dr. Tester 2", email="doctest2@test.org", role=UserRole.DOCTOR, is_active=True)
    db_session.add(doctor)
    db_session.flush()

    admission = Admission(
        patient_id=patient.id,
        attending_doctor_id=doctor.id,
        primary_diagnosis="Pneumonia",
        status=AdmissionStatus.DISCHARGING,
    )
    db_session.add(admission)
    db_session.commit()

    svc = ClinicalDocumentService(db_session, ocr_provider=FailingOCR())
    doc = svc.upload_document(
        admission_id=admission.id,
        uploader=doctor,
        file_name="unreadable_scan.png",
        file_bytes=b"damaged image bytes",
        mime_type="image/png",
    )

    assert doc.ocr_status == DocumentStatus.OCR_FAILED
    assert "OCR scanner optical sensor timeout" in doc.error_message

    # Test retry with working provider
    svc.ocr_provider = DefaultClinicalOCRProvider()
    retried_doc = svc.process_ocr_and_extract(doc.id, file_bytes=b"repaired scan bytes")
    assert retried_doc.ocr_status == DocumentStatus.EXTRACTION_COMPLETED
    assert retried_doc.ocr_raw_text is not None
