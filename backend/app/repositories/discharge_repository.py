from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.discharge_report import DischargeReport, DischargeReportStatus
from app.repositories.base import BaseRepository


class DischargeRepository(BaseRepository[DischargeReport]):
    def __init__(self, db: Session):
        super().__init__(DischargeReport, db)

    def get_by_admission_id(self, admission_id: int) -> Optional[DischargeReport]:
        return self.db.query(DischargeReport).filter(DischargeReport.admission_id == admission_id).first()

    def get_by_status(self, status: DischargeReportStatus) -> List[DischargeReport]:
        return self.db.query(DischargeReport).filter(DischargeReport.status == status).all()
