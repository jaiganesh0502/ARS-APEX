import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.models.transfer import Transfer
from app.schemas.transfer import HospitalMatchRead
from app.services.distance_service import DistanceService

logger = logging.getLogger(__name__)


class HospitalMatchingService:
    """
    Deterministic, explainable matching engine that ranks partner receiving hospitals
    based on Required Specialty (mandatory), Available Capacity, and Distance.
    """

    def __init__(self, db: Session, distance_service: Optional[DistanceService] = None):
        self.db = db
        self.distance_service = distance_service or DistanceService(mode="local")

    def find_matches_for_transfer(self, transfer: Transfer) -> List[HospitalMatchRead]:
        """
        Rank suitable partner hospitals for a specific transfer case.
        """
        sending_hospital = self.db.get(Hospital, transfer.sending_hospital_id)
        if not sending_hospital:
            logger.warning(
                "Sending hospital %s not found for transfer %s",
                transfer.sending_hospital_id,
                transfer.id,
            )
            return []

        return self.rank_hospitals(
            sending_hospital=sending_hospital,
            required_specialty=transfer.required_specialty,
            emergency=transfer.emergency,
        )

    def rank_hospitals(
        self,
        sending_hospital: Hospital,
        required_specialty: str,
        emergency: bool = False,
    ) -> List[HospitalMatchRead]:
        """
        Rank all partner hospitals in the network for a required specialty and urgency.
        """
        normalized_specialty = required_specialty.strip().lower()

        # Query all hospitals other than the sending hospital
        candidate_hospitals = (
            self.db.query(Hospital)
            .filter(Hospital.id != sending_hospital.id)
            .all()
        )

        matches: List[HospitalMatchRead] = []

        for hospital in candidate_hospitals:
            # 1. Specialty check
            # Check hospital.specialties list (case-insensitive)
            supported_specialties = [s.strip().lower() for s in (hospital.specialties or [])]
            
            # Also find matching capacity record
            capacity_records = (
                self.db.query(HospitalCapacity)
                .filter(
                    HospitalCapacity.hospital_id == hospital.id,
                )
                .all()
            )
            
            matching_capacity = next(
                (c for c in capacity_records if c.specialty.strip().lower() == normalized_specialty),
                None
            )

            # Mandatory specialty check: must be in specialties list OR have capacity record
            is_specialty_supported = (
                normalized_specialty in supported_specialties
                or matching_capacity is not None
            )

            if not is_specialty_supported:
                continue

            # 2. Capacity check: available beds must be > 0
            available_beds = matching_capacity.available_beds if matching_capacity else 0
            total_beds = matching_capacity.total_beds if matching_capacity else 0

            if available_beds <= 0:
                # Excluded: no available beds for the required specialty
                continue

            # 3. Distance calculation
            distance_km = self.distance_service.calculate_distance_km(
                origin=(sending_hospital.latitude, sending_hospital.longitude),
                destination=(hospital.latitude, hospital.longitude),
            )

            # 4. Deterministic Scoring
            # Capacity score: 0 to 50
            capacity_score = round(min(available_beds / 5.0, 1.0) * 50.0, 1)

            # Distance score: 0 to 50
            if distance_km <= 5.0:
                distance_score = 50.0
            elif distance_km <= 10.0:
                distance_score = 40.0
            elif distance_km <= 20.0:
                distance_score = 30.0
            elif distance_km <= 40.0:
                distance_score = 20.0
            else:
                distance_score = 10.0

            # Weighting by urgency
            if emergency:
                # Distance 65%, Capacity 35%
                total_score = (distance_score * 0.65 + capacity_score * 0.35) * 2.0
            else:
                # Distance 50%, Capacity 50%
                total_score = (distance_score * 0.50 + capacity_score * 0.50) * 2.0

            match_score = int(round(total_score))
            match_score = max(0, min(100, match_score))

            # 5. Deterministic Match Explanations
            bed_str = "1 bed" if available_beds == 1 else f"{available_beds} beds"
            specialty_display = matching_capacity.specialty if matching_capacity else required_specialty
            reasons = [
                f"{specialty_display} services available",
                f"{bed_str} currently available",
            ]

            if distance_km <= 5.0:
                reasons.append(f"Immediate local transit zone ({distance_km} km away)")
            elif distance_km <= 10.0:
                reasons.append(f"Nearby facility ({distance_km} km away)")
            else:
                reasons.append(f"Transit distance: {distance_km} km")

            if emergency:
                reasons.append("Emergency transfer: transit proximity prioritized (65% weight)")

            matches.append(
                HospitalMatchRead(
                    hospital_id=hospital.id,
                    hospital_name=hospital.name,
                    required_specialty=specialty_display,
                    available_beds=available_beds,
                    total_beds=total_beds,
                    distance_km=distance_km,
                    capacity_score=capacity_score,
                    distance_score=distance_score,
                    match_score=match_score,
                    match_reasons=reasons,
                    emergency=emergency,
                    contact_number=hospital.contact_number,
                    is_recommended=False,
                )
            )

        # 6. Sort matches by score descending, then distance ascending
        matches.sort(key=lambda m: (-m.match_score, m.distance_km, -m.available_beds))

        # Flag the first match as Recommended
        if matches:
            matches[0].is_recommended = True

        return matches
