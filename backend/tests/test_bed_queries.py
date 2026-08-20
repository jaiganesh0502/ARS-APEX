from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import event

from app.models import (
    Admission,
    AdmissionStatus,
    Bed,
    BedStatus,
    DischargeReport,
    DischargeReportStatus,
    MedicalRecord,
    Patient,
    User,
    UserRole,
    WorkflowEvent,
)


@pytest.fixture
def operational_beds(db_session):
    """Seed the operational states consumed by the bed read API."""
    doctor = User(name="Dr. Query", email="query.doctor@example.test", role=UserRole.DOCTOR)
    db_session.add(doctor)
    db_session.flush()

    beds = {
        "occupied": Bed(ward="General Medicine", bed_number="GM-01", status=BedStatus.OCCUPIED),
        "vacating": Bed(ward="General Medicine", bed_number="GM-02", status=BedStatus.VACATING),
        "cleaning": Bed(ward="General Medicine", bed_number="GM-03", status=BedStatus.CLEANING),
        "available": Bed(ward="General Medicine", bed_number="GM-04", status=BedStatus.AVAILABLE),
        "reserved": Bed(ward="General Medicine", bed_number="GM-05", status=BedStatus.RESERVED),
        "empty_ward": Bed(ward="", bed_number="EMPTY-01", status=BedStatus.AVAILABLE),
        "ineligible": Bed(ward="Surgery", bed_number="SU-01", status=BedStatus.OCCUPIED),
    }
    db_session.add_all(beds.values())
    db_session.flush()

    occupied_patient = Patient(
        patient_code="PT-1001", first_name="Arun", last_name="Kumar",
        date_of_birth=date(1974, 4, 18), gender="Male",
    )
    vacating_patient = Patient(
        patient_code="PT-1002", first_name="Meera", last_name="Nair",
        date_of_birth=date(1968, 9, 7), gender="Female",
    )
    former_patient = Patient(
        patient_code="PT-1003", first_name="Ishaan", last_name="Rao",
        date_of_birth=date(1960, 6, 9), gender="Male",
    )
    ineligible_patient = Patient(
        patient_code="PT-1004", first_name="Rina", last_name="Das",
        date_of_birth=date(1984, 10, 21), gender="Female",
    )
    db_session.add_all([occupied_patient, vacating_patient, former_patient, ineligible_patient])
    db_session.flush()

    beds["occupied"].current_patient_id = occupied_patient.id
    beds["vacating"].current_patient_id = vacating_patient.id
    beds["ineligible"].current_patient_id = ineligible_patient.id
    admissions = {
        "occupied": Admission(
            patient_id=occupied_patient.id, bed_id=beds["occupied"].id,
            admission_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
            primary_diagnosis="Community Acquired Pneumonia", attending_doctor_id=doctor.id,
            status=AdmissionStatus.DISCHARGING,
        ),
        "vacating": Admission(
            patient_id=vacating_patient.id, bed_id=beds["vacating"].id,
            admission_date=datetime(2026, 8, 11, tzinfo=timezone.utc),
            primary_diagnosis="Acute Ischemic Stroke", attending_doctor_id=doctor.id,
            status=AdmissionStatus.DISCHARGING,
        ),
        "former": Admission(
            patient_id=former_patient.id, bed_id=beds["available"].id,
            admission_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
            primary_diagnosis="Resolved Appendicitis", attending_doctor_id=doctor.id,
            status=AdmissionStatus.DISCHARGED,
        ),
        "ineligible": Admission(
            patient_id=ineligible_patient.id, bed_id=beds["ineligible"].id,
            admission_date=datetime(2026, 8, 12, tzinfo=timezone.utc),
            primary_diagnosis="Postoperative Recovery", attending_doctor_id=doctor.id,
            status=AdmissionStatus.DISCHARGING,
        ),
    }
    db_session.add_all(admissions.values())
    db_session.flush()

    oldest = datetime(2026, 8, 18, 8, tzinfo=timezone.utc)
    approved_report = DischargeReport(
        patient_id=occupied_patient.id, admission_id=admissions["occupied"].id,
        generated_content="Approved report", generation_model="test-model",
        status=DischargeReportStatus.APPROVED,
        approved_by=doctor.id,
        approved_at=oldest,
    )
    missing_event_report = DischargeReport(
        patient_id=ineligible_patient.id, admission_id=admissions["ineligible"].id,
        generated_content="Approved but unaudited report", generation_model="test-model",
        status=DischargeReportStatus.APPROVED,
    )
    db_session.add_all([approved_report, missing_event_report])
    db_session.flush()

    db_session.add_all([
        WorkflowEvent(
            event_type="report_approved", entity_type="discharge_report", entity_id=approved_report.id,
            trusted_provenance=True,
            payload={
                "report_id": approved_report.id,
                "patient_id": occupied_patient.id,
                "admission_id": admissions["occupied"].id,
                "approved_by": doctor.id,
                "approved_at": oldest.isoformat(),
            },
            created_at=oldest,
        ),
        WorkflowEvent(
            event_type="bed_available", entity_type="bed", entity_id=beds["occupied"].id,
            trusted_provenance=True,
            payload={
                "bed_id": beds["occupied"].id,
                "patient_id": occupied_patient.id,
                "admission_id": admissions["occupied"].id,
                "previous_status": "cleaning",
                "new_status": "available",
                "timestamp": oldest.isoformat(),
                "actor_user_id": doctor.id,
                "actor_name": doctor.name,
                "actor_role": doctor.role.value,
            },
            created_at=oldest,
        ),
        WorkflowEvent(
            event_type="bed_release_started", entity_type="bed", entity_id=beds["occupied"].id,
            trusted_provenance=True,
            payload={
                "bed_id": beds["occupied"].id,
                "patient_id": occupied_patient.id,
                "admission_id": admissions["occupied"].id,
                "report_id": approved_report.id,
                "previous_status": "occupied",
                "new_status": "vacating",
                "timestamp": (oldest + timedelta(hours=1)).isoformat(),
                "actor_user_id": doctor.id,
                "actor_name": doctor.name,
                "actor_role": doctor.role.value,
            },
            created_at=oldest + timedelta(hours=1),
        ),
    ])
    db_session.commit()
    return {"beds": beds, "admissions": admissions}


def _add_release_case(
    db_session,
    doctor_id,
    bed_number,
    *,
    bed_status=BedStatus.OCCUPIED,
    admission_status=AdmissionStatus.DISCHARGING,
    report_status=DischargeReportStatus.APPROVED,
    event_entity_id=None,
    inconsistent_assignment=False,
):
    patient = Patient(
        patient_code=f"CASE-{bed_number}", first_name="Boundary", last_name=bed_number,
        date_of_birth=date(1980, 1, 1), gender="Other",
    )
    bed = Bed(ward="Boundary", bed_number=bed_number, status=bed_status)
    db_session.add_all([patient, bed])
    db_session.flush()
    bed.current_patient_id = patient.id
    admission = Admission(
        patient_id=patient.id,
        bed_id=None if inconsistent_assignment else bed.id,
        admission_date=datetime(2026, 8, 14, tzinfo=timezone.utc),
        primary_diagnosis="Boundary diagnosis",
        attending_doctor_id=doctor_id,
        status=admission_status,
    )
    db_session.add(admission)
    db_session.flush()
    approval_time = datetime(2026, 8, 19, 8, tzinfo=timezone.utc)
    report = DischargeReport(
        patient_id=patient.id, admission_id=admission.id,
        generated_content="Boundary report", generation_model="test-model", status=report_status,
        approved_by=doctor_id if report_status == DischargeReportStatus.APPROVED else None,
        approved_at=approval_time if report_status == DischargeReportStatus.APPROVED else None,
    )
    db_session.add(report)
    db_session.flush()
    if event_entity_id is not False:
        db_session.add(WorkflowEvent(
            event_type="report_approved", entity_type="discharge_report",
            entity_id=report.id if event_entity_id is None else event_entity_id,
            trusted_provenance=True,
            payload={
                "report_id": report.id,
                "patient_id": patient.id,
                "admission_id": admission.id,
                "approved_by": doctor_id,
                "approved_at": approval_time.isoformat(),
            },
            created_at=approval_time,
        ))
    db_session.commit()
    return bed


def test_list_beds_filters_operational_summaries_by_status_and_exact_ward(client, operational_beds):
    """Changing the query to omit the assignment must fail this contract."""
    response = client.get("/api/beds", params={"status": "occupied", "ward": "General Medicine"})

    assert response.status_code == 200
    assert [item["status"] for item in response.json()] == ["occupied"]
    assert response.json()[0]["patient_code"] == "PT-1001"
    assert response.json()[0]["release_eligible"] is True


def test_list_beds_includes_all_statuses_and_available_bed_has_no_current_patient(client, operational_beds):
    """Leaking a former patient into an available bed must fail this contract."""
    response = client.get("/api/beds")

    assert response.status_code == 200
    payload = response.json()
    assert {item["status"] for item in payload} == {
        "occupied", "vacating", "cleaning", "available", "reserved",
    }
    available = next(item for item in payload if item["bed_number"] == "GM-04")
    assert available["current_patient_id"] is None
    assert available["patient_name"] is None
    assert available["patient_code"] is None


def test_bed_detail_exposes_operational_context_and_newest_transition_first(client, operational_beds):
    """Reversing history order or dropping the matching admission must fail this contract."""
    bed_id = operational_beds["beds"]["occupied"].id
    admission_id = operational_beds["admissions"]["occupied"].id

    detail = client.get(f"/api/beds/{bed_id}")

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["admission_id"] == admission_id
    assert payload["primary_diagnosis"] == "Community Acquired Pneumonia"
    assert [event["event_type"] for event in payload["transition_history"]] == [
        "bed_release_started", "bed_available",
    ]
    assert payload["transition_history"][0]["previous_status"] == "occupied"
    assert payload["transition_history"][0]["new_status"] == "vacating"


def test_missing_bed_detail_returns_controlled_404(client):
    """Returning a null or server error for a missing bed must fail this contract."""
    response = client.get("/api/beds/999999")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Bed not found"


def test_release_eligibility_requires_approved_report_audit_event(client, operational_beds):
    """Treating an approved but unaudited report as releasable must fail this contract."""
    response = client.get("/api/beds", params={"status": "occupied"})

    assert response.status_code == 200
    eligibility = {item["bed_number"]: item["release_eligible"] for item in response.json()}
    assert eligibility == {"GM-01": True, "SU-01": False}


def test_release_eligibility_requires_consistent_bed_assignment(client, db_session, operational_beds):
    """Using a patient match without the same bed assignment must fail this contract."""
    doctor_id = operational_beds["admissions"]["occupied"].attending_doctor_id
    bed = _add_release_case(db_session, doctor_id, "BAD-ASSIGN", inconsistent_assignment=True)

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    assert response.json()["release_eligible"] is False


def test_release_eligibility_requires_discharging_admission(client, db_session, operational_beds):
    """Treating an admitted patient as releasable must fail this contract."""
    doctor_id = operational_beds["admissions"]["occupied"].attending_doctor_id
    bed = _add_release_case(
        db_session, doctor_id, "NOT-DISCHARGING", admission_status=AdmissionStatus.ADMITTED,
    )

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    assert response.json()["release_eligible"] is False


def test_release_eligibility_requires_an_approved_report(client, db_session, operational_beds):
    """Treating a generated report as approved must fail this contract."""
    doctor_id = operational_beds["admissions"]["occupied"].attending_doctor_id
    bed = _add_release_case(
        db_session, doctor_id, "UNAPPROVED", report_status=DischargeReportStatus.GENERATED,
    )

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    assert response.json()["release_eligible"] is False


def test_release_eligibility_requires_an_event_for_the_matching_report(client, db_session, operational_beds):
    """Pairing a report with another report's approval event must fail this contract."""
    doctor_id = operational_beds["admissions"]["occupied"].attending_doctor_id
    bed = _add_release_case(db_session, doctor_id, "MISMATCHED-EVENT", event_entity_id=999999)

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    assert response.json()["release_eligible"] is False


def test_release_eligibility_rejects_an_exact_untrusted_approval_event(
    client, db_session, operational_beds,
):
    """A perfect legacy clone must not authorize the release workflow."""
    event = db_session.query(WorkflowEvent).filter_by(event_type="report_approved").one()
    event.trusted_provenance = False
    db_session.commit()

    response = client.get(f"/api/beds/{operational_beds['beds']['occupied'].id}")

    assert response.status_code == 200
    assert response.json()["release_eligible"] is False


def test_release_eligibility_rejects_forged_approval_payload_relations(
    client, db_session, operational_beds,
):
    """A trusted row whose payload names another patient must not authorize release."""
    event = db_session.query(WorkflowEvent).filter_by(event_type="report_approved").one()
    event.payload = {**event.payload, "patient_id": 999999}
    db_session.commit()

    response = client.get(f"/api/beds/{operational_beds['beds']['occupied'].id}")

    assert response.status_code == 200
    assert response.json()["release_eligible"] is False


def test_release_eligibility_rejects_a_non_occupied_bed(client, db_session, operational_beds):
    """Treating a vacating bed as eligible to start release must fail this contract."""
    doctor_id = operational_beds["admissions"]["occupied"].attending_doctor_id
    bed = _add_release_case(db_session, doctor_id, "VACATING", bed_status=BedStatus.VACATING)

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    assert response.json()["release_eligible"] is False


def test_available_detail_uses_newest_discharged_admission_date_and_hides_current_patient(
    client, db_session, operational_beds,
):
    """Sorting historical context by mutable update time must fail this contract."""
    former = operational_beds["admissions"]["former"]
    former.updated_at = datetime(2026, 8, 20, tzinfo=timezone.utc)
    newer = Admission(
        patient_id=former.patient_id,
        bed_id=operational_beds["beds"]["available"].id,
        admission_date=datetime(2026, 8, 2, tzinfo=timezone.utc),
        primary_diagnosis="Most Recent Discharged Diagnosis",
        attending_doctor_id=former.attending_doctor_id,
        status=AdmissionStatus.DISCHARGED,
        updated_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    db_session.add(newer)
    db_session.commit()

    response = client.get(f"/api/beds/{operational_beds['beds']['available'].id}")

    assert response.status_code == 200
    assert response.json()["admission_id"] == newer.id
    assert response.json()["primary_diagnosis"] == "Most Recent Discharged Diagnosis"
    assert response.json()["current_patient_id"] is None
    assert response.json()["patient_name"] is None
    assert response.json()["patient_code"] is None


def test_bed_detail_hides_private_patient_and_clinical_fields(client, db_session, operational_beds):
    """Adding demographic or medical-record fields to bed detail must fail this contract."""
    admission = operational_beds["admissions"]["occupied"]
    db_session.add(MedicalRecord(
        patient_id=admission.patient_id, admission_id=admission.id,
        diagnosis="Community Acquired Pneumonia", treatment_course="Private treatment", notes="Private note",
    ))
    db_session.commit()

    response = client.get(f"/api/beds/{operational_beds['beds']['occupied'].id}")

    assert response.status_code == 200
    assert {"phone", "emergency_contact", "date_of_birth", "medical_record", "notes"}.isdisjoint(response.json())


def test_bed_detail_excludes_forged_and_unrelated_legacy_events(client, db_session, operational_beds):
    """Malformed or unrelated legacy events must never enter operational bed history."""
    bed = operational_beds["beds"]["occupied"]
    db_session.add_all([
        WorkflowEvent(
            event_type="legacy-list-payload", entity_type="bed", entity_id=bed.id,
            payload=["legacy"], created_at=datetime(2026, 8, 19, 12, tzinfo=timezone.utc),
        ),
        WorkflowEvent(
            event_type="legacy-invalid-status", entity_type="bed", entity_id=bed.id,
            payload={"previous_status": "unknown", "new_status": "available"},
            created_at=datetime(2026, 8, 19, 11, tzinfo=timezone.utc),
        ),
    ])
    db_session.commit()

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    event_types = [item["event_type"] for item in response.json()["transition_history"]]
    assert event_types == ["bed_release_started", "bed_available"]
    assert "legacy-list-payload" not in event_types
    assert "legacy-invalid-status" not in event_types


def test_bed_detail_excludes_an_exact_untrusted_transition_clone(
    client, db_session, operational_beds,
):
    """An exact valid-shaped legacy clone must not appear in operational history."""
    bed = operational_beds["beds"]["occupied"]
    source = db_session.query(WorkflowEvent).filter_by(
        event_type="bed_release_started", entity_type="bed", entity_id=bed.id,
    ).one()
    db_session.add(WorkflowEvent(
        event_type=source.event_type,
        entity_type=source.entity_type,
        entity_id=source.entity_id,
        status=source.status,
        trusted_provenance=False,
        payload=dict(source.payload),
        created_at=source.created_at,
    ))
    db_session.commit()

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    assert [item["event_type"] for item in response.json()["transition_history"]] == [
        "bed_release_started", "bed_available",
    ]


@pytest.mark.parametrize(
    ("payload_field", "wrong_value", "created_at_offset"),
    [
        ("actor_user_id", 999997, timedelta()),
        ("report_id", 999998, timedelta()),
        (None, None, timedelta(hours=1)),
    ],
)
def test_bed_detail_excludes_trusted_events_with_broken_relational_correlation(
    client, db_session, operational_beds,
    payload_field, wrong_value, created_at_offset,
):
    """Missing actor/report rows or event-time mismatch must hide the audit row."""
    bed = operational_beds["beds"]["occupied"]
    source = db_session.query(WorkflowEvent).filter_by(
        event_type="bed_release_started", entity_type="bed", entity_id=bed.id,
    ).one()
    payload = dict(source.payload)
    if payload_field is not None:
        payload[payload_field] = wrong_value
    db_session.add(WorkflowEvent(
        event_type=source.event_type,
        entity_type=source.entity_type,
        entity_id=source.entity_id,
        status=source.status,
        trusted_provenance=True,
        payload=payload,
        created_at=source.created_at + created_at_offset,
    ))
    db_session.commit()

    response = client.get(f"/api/beds/{bed.id}")

    assert response.status_code == 200
    assert sum(
        item["event_type"] == "bed_release_started"
        for item in response.json()["transition_history"]
    ) == 1


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=101"])
def test_bed_list_rejects_invalid_pagination(client, query):
    """Accepting out-of-range pagination parameters must fail this contract."""
    response = client.get(f"/api/beds?{query}")

    assert response.status_code == 422


def test_bed_list_paginates_and_filters_the_empty_ward_exactly(client, operational_beds):
    """Dropping an explicit empty ward filter must fail this contract."""
    filtered = client.get("/api/beds", params={"ward": "", "skip": 0, "limit": 1})
    paged = client.get("/api/beds", params={"ward": "General Medicine", "skip": 1, "limit": 2})

    assert filtered.status_code == 200
    assert [item["bed_number"] for item in filtered.json()] == ["EMPTY-01"]
    assert paged.status_code == 200
    assert [item["bed_number"] for item in paged.json()] == ["GM-02", "GM-03"]


def test_bed_list_uses_a_bounded_number_of_database_queries(client, db_session, operational_beds):
    """Adding per-bed queries to the operational list must fail this contract."""
    statements = []

    def count_queries(*args):
        statements.append(args[2])

    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", count_queries)
    try:
        response = client.get("/api/beds")
    finally:
        event.remove(connection, "before_cursor_execute", count_queries)

    assert response.status_code == 200
    assert len(statements) <= 5
