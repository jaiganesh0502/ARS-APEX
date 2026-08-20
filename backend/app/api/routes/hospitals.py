from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.schemas.hospital import HospitalRead, HospitalCreate
from app.schemas.hospital_capacity import HospitalCapacityRead, HospitalCapacityUpdate

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


@router.get("", response_model=List[HospitalRead])
def list_hospitals(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Hospital).offset(skip).limit(limit).all()


@router.get("/{hospital_id}", response_model=HospitalRead)
def get_hospital(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital


@router.post("", response_model=HospitalRead, status_code=status.HTTP_201_CREATED)
def create_hospital(hospital_in: HospitalCreate, db: Session = Depends(get_db)):
    hospital = Hospital(**hospital_in.model_dump())
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital


@router.get("/{hospital_id}/capacities", response_model=List[HospitalCapacityRead])
def list_hospital_capacities(hospital_id: int, db: Session = Depends(get_db)):
    return db.query(HospitalCapacity).filter(HospitalCapacity.hospital_id == hospital_id).all()


@router.put("/capacities/{capacity_id}", response_model=HospitalCapacityRead)
def update_capacity(capacity_id: int, update_in: HospitalCapacityUpdate, db: Session = Depends(get_db)):
    cap = db.query(HospitalCapacity).filter(HospitalCapacity.id == capacity_id).first()
    if not cap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capacity record not found")
    cap.available_beds = update_in.available_beds
    cap.total_beds = update_in.total_beds
    db.commit()
    db.refresh(cap)
    return cap
