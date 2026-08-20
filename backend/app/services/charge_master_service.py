from decimal import Decimal
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.charge_master import ChargeCategory, ChargeMasterItem

logger = logging.getLogger(__name__)

DEFAULT_CHARGE_CATALOG = [
    # Room charges (per day)
    {"code": "ROOM_GEN_WARD", "category": ChargeCategory.ROOM, "name": "General Medical Ward (Daily)", "unit_price": Decimal("1500.00"), "description": "Standard inpatient ward accommodation and nursing"},
    {"code": "ROOM_SURG_WARD", "category": ChargeCategory.ROOM, "name": "General Surgery Ward (Daily)", "unit_price": Decimal("2200.00"), "description": "Post-operative surgical ward accommodation"},
    {"code": "ROOM_ICU", "category": ChargeCategory.ROOM, "name": "Intensive Care Unit (ICU Daily)", "unit_price": Decimal("8500.00"), "description": "Continuous hemodynamic monitoring & specialized ICU care"},
    {"code": "ROOM_CARDIAC_ICU", "category": ChargeCategory.ROOM, "name": "Cardiac Intensive Care (CCU Daily)", "unit_price": Decimal("9500.00"), "description": "Critical cardiac care and 24/7 telemetry"},
    
    # Procedure charges
    {"code": "PROC_APPENDECTOMY", "category": ChargeCategory.PROCEDURE, "name": "Laparoscopic Appendectomy", "unit_price": Decimal("35000.00"), "description": "Minimally invasive surgical removal of appendix"},
    {"code": "PROC_CORONARY_ANGIO", "category": ChargeCategory.PROCEDURE, "name": "Coronary Angiography", "unit_price": Decimal("22000.00"), "description": "Diagnostic catheterization and vessel imaging"},
    {"code": "PROC_WOUND_DEBRIDEMENT", "category": ChargeCategory.PROCEDURE, "name": "Complex Wound Debridement & Dressing", "unit_price": Decimal("4500.00"), "description": "Sterile surgical debridement and tissue dressing"},
    {"code": "PROC_NEBULIZATION", "category": ChargeCategory.PROCEDURE, "name": "Nebulization & Respiratory Therapy", "unit_price": Decimal("800.00"), "description": "Bronchodilator respiratory therapy per session"},

    # Investigation & Lab charges
    {"code": "LAB_CBC", "category": ChargeCategory.INVESTIGATION, "name": "Complete Blood Count (CBC) with Platelets", "unit_price": Decimal("650.00"), "description": "Hematological profile analysis"},
    {"code": "LAB_METABOLIC", "category": ChargeCategory.INVESTIGATION, "name": "Comprehensive Metabolic Panel (CMP)", "unit_price": Decimal("1200.00"), "description": "Electrolytes, renal function, liver enzymes"},
    {"code": "LAB_CARDIAC_ENZYMES", "category": ChargeCategory.INVESTIGATION, "name": "Cardiac Biomarkers (Troponin-I, CPK-MB)", "unit_price": Decimal("1800.00"), "description": "Serum cardiac damage markers"},
    {"code": "RAD_CHEST_XRAY", "category": ChargeCategory.INVESTIGATION, "name": "Digital Chest X-Ray (PA View)", "unit_price": Decimal("900.00"), "description": "Radiological chest imaging"},
    {"code": "RAD_ULTRASOUND_ABD", "category": ChargeCategory.INVESTIGATION, "name": "Ultrasound Whole Abdomen", "unit_price": Decimal("2500.00"), "description": "Diagnostic abdominal sonography"},
    {"code": "TEST_ECG", "category": ChargeCategory.INVESTIGATION, "name": "12-Lead Electrocardiogram (ECG)", "unit_price": Decimal("500.00"), "description": "Cardiac electrical activity recording"},

    # Consultations & Services
    {"code": "CONS_ATTENDING", "category": ChargeCategory.CONSULTATION, "name": "Attending Physician Daily Rounds", "unit_price": Decimal("1000.00"), "description": "Daily inpatient clinical review by senior physician"},
    {"code": "CONS_SPECIALIST", "category": ChargeCategory.CONSULTATION, "name": "Specialist Cross-Consultation", "unit_price": Decimal("2000.00"), "description": "Sub-specialty consultation and advisory"},
    {"code": "SERV_NURSING", "category": ChargeCategory.SERVICE, "name": "Daily Inpatient Nursing Care", "unit_price": Decimal("800.00"), "description": "24-hour nursing administration & vital monitoring"},
    {"code": "SERV_DISCHARGE_MGMT", "category": ChargeCategory.SERVICE, "name": "Discharge Coordination & Documentation", "unit_price": Decimal("600.00"), "description": "Care transition planning and formal records packaging"},

    # Medications
    {"code": "MED_AMOX_CLAV_625", "category": ChargeCategory.MEDICATION, "name": "Amoxicillin-Clavulanate 625mg (Course)", "unit_price": Decimal("480.00"), "description": "Broad-spectrum antibacterial therapy"},
    {"code": "MED_PARACETAMOL_650", "category": ChargeCategory.MEDICATION, "name": "Paracetamol 650mg Tabs (Strip)", "unit_price": Decimal("90.00"), "description": "Antipyretic and analgesic medication"},
    {"code": "MED_PANTOPRAZOLE_40", "category": ChargeCategory.MEDICATION, "name": "IV Pantoprazole 40mg (Vials)", "unit_price": Decimal("350.00"), "description": "Gastroprotective proton pump inhibitor"},
    {"code": "MED_IV_FLUIDS_NS", "category": ChargeCategory.MEDICATION, "name": "IV Normal Saline 0.9% 500ml (x3)", "unit_price": Decimal("450.00"), "description": "Intravenous hydration and electrolyte maintenance"},
]


class ChargeMasterService:
    def __init__(self, db: Session):
        self.db = db

    def list_items(self, category: Optional[ChargeCategory] = None, active_only: bool = True) -> List[ChargeMasterItem]:
        query = self.db.query(ChargeMasterItem)
        if category:
            query = query.filter(ChargeMasterItem.category == category)
        if active_only:
            query = query.filter(ChargeMasterItem.is_active == True)
        return query.order_by(ChargeMasterItem.category, ChargeMasterItem.name).all()

    def get_by_code(self, code: str) -> Optional[ChargeMasterItem]:
        return self.db.query(ChargeMasterItem).filter(ChargeMasterItem.code == code).first()

    def seed_defaults_if_empty(self):
        count = self.db.query(ChargeMasterItem).count()
        if count == 0:
            logger.info("Seeding standard hospital ChargeMaster catalog...")
            for item_data in DEFAULT_CHARGE_CATALOG:
                item = ChargeMasterItem(**item_data)
                self.db.add(item)
            self.db.flush()
            logger.info("Successfully seeded %d ChargeMaster items.", len(DEFAULT_CHARGE_CATALOG))
