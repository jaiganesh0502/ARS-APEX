from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    OCR_PROCESSING = "ocr_processing"
    OCR_COMPLETED = "ocr_completed"
    OCR_FAILED = "ocr_failed"
    EXTRACTION_PROCESSING = "extraction_processing"
    EXTRACTION_COMPLETED = "extraction_completed"


class ClinicalDocumentType(str, enum.Enum):
    DOCTOR_HANDWRITTEN_NOTES = "doctor_handwritten_notes"
    PROGRESS_NOTES = "progress_notes"
    TREATMENT_SHEET = "treatment_sheet"
    MEDICATION_SHEET = "medication_sheet"
    INVESTIGATION_SHEET = "investigation_sheet"
    PROCEDURE_NOTES = "procedure_notes"
    SCANNED_FORM = "scanned_form"


class ClinicalDocument(Base):
    __tablename__ = "clinical_documents"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    document_type = Column(String(50), default=ClinicalDocumentType.DOCTOR_HANDWRITTEN_NOTES.value, nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)

    ocr_status = Column(
        Enum(
            DocumentStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=DocumentStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    ocr_raw_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    structured_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    admission = relationship("Admission", backref="clinical_documents")
    patient = relationship("Patient", backref="clinical_documents")
    uploader = relationship("User", foreign_keys=[uploader_id])
