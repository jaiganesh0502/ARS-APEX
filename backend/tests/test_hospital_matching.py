import pytest
from datetime import datetime, timezone
from app.models.hospital import Hospital
from app.models.hospital_capacity import HospitalCapacity
from app.services.distance_service import DistanceService, calculate_haversine_distance_km
from app.services.hospital_matching_service import HospitalMatchingService


def test_haversine_distance_known_coordinates():
    # Distance between San Francisco (37.7749, -122.4194) and Oakland (37.8044, -122.2711) is ~13.5 km
    dist = calculate_haversine_distance_km(37.7749, -122.4194, 37.8044, -122.2711)
    assert 12.0 <= dist <= 15.0
    assert isinstance(dist, float)


def test_distance_service_local_mode():
    service = DistanceService(mode="local")
    dist = service.calculate_distance_km((37.7749, -122.4194), (37.7749, -122.4194))
    assert dist == 0.0


def test_matching_specialty_filtering_and_zero_capacity_exclusion(db_session):
    # Setup sending hospital
    sending = Hospital(
        name="Sending Host Hospital",
        latitude=37.7749,
        longitude=-122.4194,
        specialties=["General Medicine", "Cardiology"],
        contact_number="111",
    )
    # Hospital A: Cardiology supported, 3 available beds, 2.4 km away
    hosp_a = Hospital(
        name="Cardio Clinic A",
        latitude=37.7550,
        longitude=-122.4300,
        specialties=["Cardiology"],
        contact_number="222",
    )
    # Hospital B: Cardiology supported, 0 available beds (full)
    hosp_b = Hospital(
        name="Cardio Clinic B Full",
        latitude=37.7600,
        longitude=-122.4200,
        specialties=["Cardiology"],
        contact_number="333",
    )
    # Hospital C: Orthopedics only, no Cardiology
    hosp_c = Hospital(
        name="Ortho Center C",
        latitude=37.7700,
        longitude=-122.4100,
        specialties=["Orthopedics"],
        contact_number="444",
    )
    db_session.add_all([sending, hosp_a, hosp_b, hosp_c])
    db_session.flush()

    cap_a = HospitalCapacity(hospital_id=hosp_a.id, specialty="Cardiology", total_beds=10, available_beds=3)
    cap_b = HospitalCapacity(hospital_id=hosp_b.id, specialty="Cardiology", total_beds=10, available_beds=0)
    cap_c = HospitalCapacity(hospital_id=hosp_c.id, specialty="Orthopedics", total_beds=10, available_beds=5)
    db_session.add_all([cap_a, cap_b, cap_c])
    db_session.commit()

    matching_service = HospitalMatchingService(db_session)
    matches = matching_service.rank_hospitals(sending_hospital=sending, required_specialty="Cardiology")

    # Only Hospital A should be returned
    assert len(matches) == 1
    assert matches[0].hospital_id == hosp_a.id
    assert matches[0].hospital_name == "Cardio Clinic A"
    assert matches[0].available_beds == 3
    assert matches[0].is_recommended is True
    assert "Cardiology services available" in matches[0].match_reasons[0]


def test_matching_emergency_vs_non_emergency_weighting(db_session):
    """
    Hospital A: Closer (3 km -> distance score 50), but fewer beds (2 beds -> capacity score 20)
    Hospital B: Farther (15 km -> distance score 30), but more beds (5 beds -> capacity score 50)

    Non-Emergency (50% distance, 50% capacity):
      Hospital A: (50*0.5 + 20*0.5)*2 = 70
      Hospital B: (30*0.5 + 50*0.5)*2 = 80
      -> Hospital B ranks HIGHER in non-emergency!

    Emergency (65% distance, 35% capacity):
      Hospital A: (50*0.65 + 20*0.35)*2 = (32.5 + 7.0)*2 = 79
      Hospital B: (30*0.65 + 50*0.35)*2 = (19.5 + 17.5)*2 = 74
      -> Hospital A ranks HIGHER in emergency!
    """
    sending = Hospital(name="Origin Hospital", latitude=37.7749, longitude=-122.4194, specialties=["Neurology"], contact_number="111")
    # ~3 km away
    hosp_close = Hospital(name="Close Clinic", latitude=37.7550, longitude=-122.4300, specialties=["Neurology"], contact_number="222")
    # ~15 km away
    hosp_far = Hospital(name="Far Medical Center", latitude=37.6400, longitude=-122.4194, specialties=["Neurology"], contact_number="333")
    db_session.add_all([sending, hosp_close, hosp_far])
    db_session.flush()

    cap_close = HospitalCapacity(hospital_id=hosp_close.id, specialty="Neurology", total_beds=10, available_beds=2)
    cap_far = HospitalCapacity(hospital_id=hosp_far.id, specialty="Neurology", total_beds=20, available_beds=5)
    db_session.add_all([cap_close, cap_far])
    db_session.commit()

    matching_service = HospitalMatchingService(db_session)

    # 1. Non-emergency
    non_emerg_matches = matching_service.rank_hospitals(
        sending_hospital=sending, required_specialty="Neurology", emergency=False
    )
    assert len(non_emerg_matches) == 2
    assert non_emerg_matches[0].hospital_id == hosp_far.id
    assert non_emerg_matches[0].match_score == 80
    assert non_emerg_matches[1].hospital_id == hosp_close.id
    assert non_emerg_matches[1].match_score == 70
    assert non_emerg_matches[0].is_recommended is True

    # 2. Emergency
    emerg_matches = matching_service.rank_hospitals(
        sending_hospital=sending, required_specialty="Neurology", emergency=True
    )
    assert len(emerg_matches) == 2
    assert emerg_matches[0].hospital_id == hosp_close.id
    assert emerg_matches[0].match_score == 79
    assert emerg_matches[1].hospital_id == hosp_far.id
    assert emerg_matches[1].match_score == 74
    assert emerg_matches[0].is_recommended is True


def test_matching_no_matches_returns_empty_list(db_session):
    sending = Hospital(name="Sending Hospital", latitude=37.7749, longitude=-122.4194, specialties=["Cardiology"], contact_number="111")
    db_session.add(sending)
    db_session.commit()

    matching_service = HospitalMatchingService(db_session)
    matches = matching_service.rank_hospitals(sending_hospital=sending, required_specialty="Pediatric Oncology")
    assert matches == []
