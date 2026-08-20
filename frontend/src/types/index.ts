export type UserRole = 'doctor' | 'ward_admin' | 'receiving_doctor' | 'receiving_admin';

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  created_at: string;
  updated_at: string;
}

export interface Patient {
  id: number;
  patient_code: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  blood_group?: string;
  phone?: string;
  emergency_contact?: string;
  created_at: string;
  updated_at: string;
}

export interface PatientSummary {
  id: number;
  patient_code: string;
  first_name: string;
  last_name: string;
  age: number;
  gender: string;
  primary_diagnosis?: string;
  admission_status?: AdmissionStatus;
  ward?: string;
  bed_number?: string;
}

export interface PatientListResponse {
  items: PatientSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface PatientDemographics {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  age: number;
  gender: string;
  blood_group?: string;
  phone?: string;
  emergency_contact?: string;
}

export interface PatientAdmissionDetail {
  id: number;
  admission_date: string;
  primary_diagnosis: string;
  status: AdmissionStatus;
  attending_doctor_id: number;
  attending_doctor: string;
}

export interface PatientBedDetail {
  ward: string;
  bed_number: string;
  status: BedStatus;
}

export interface PatientDetail {
  id: number;
  patient_code: string;
  demographics: PatientDemographics;
  admission?: PatientAdmissionDetail;
  bed?: PatientBedDetail;
  medical_record?: Pick<MedicalRecord, 'id' | 'diagnosis' | 'treatment_course' | 'notes' | 'created_at'>;
  medications: Array<Pick<Medication, 'id' | 'medication_name' | 'dosage' | 'frequency' | 'route' | 'start_date' | 'end_date'>>;
  vitals: Array<Pick<Vital, 'id' | 'temperature' | 'heart_rate' | 'blood_pressure_systolic' | 'blood_pressure_diastolic' | 'oxygen_saturation' | 'recorded_at'>>;
}

export type AdmissionStatus = 'admitted' | 'discharging' | 'transfer_pending' | 'transferred' | 'discharged';

export interface Admission {
  id: number;
  patient_id: number;
  admission_date: string;
  primary_diagnosis: string;
  attending_doctor_id: number;
  status: AdmissionStatus;
  bed_id?: number;
  created_at: string;
  updated_at: string;
}

export type BedStatus = 'occupied' | 'vacating' | 'cleaning' | 'available' | 'reserved';

export interface Bed {
  id: number;
  ward: string;
  bed_number: string;
  status: BedStatus;
  current_patient_id?: number;
  created_at: string;
  updated_at: string;
}

export interface BedSummary {
  id: number;
  ward: string;
  bed_number: string;
  status: BedStatus;
  current_patient_id: number | null;
  patient_name: string | null;
  patient_code: string | null;
  admission_id: number | null;
  admission_status: AdmissionStatus | null;
  primary_diagnosis: string | null;
  release_eligible: boolean;
  updated_at: string;
}

export interface BedTransitionEvent {
  event_type: string;
  previous_status: BedStatus | null;
  new_status: BedStatus | null;
  created_at: string;
}

export interface BedDetail extends BedSummary {
  transition_history: BedTransitionEvent[];
}

export interface BedCounts {
  total: number;
  occupied: number;
  vacating: number;
  cleaning: number;
  available: number;
  reserved: number;
}

export type BedAction = 'start_release' | 'patient_departed' | 'cleaning_complete';

export interface BedFilters {
  status?: BedStatus;
  ward?: string;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface MedicalRecord {
  id: number;
  patient_id: number;
  admission_id: number;
  diagnosis: string;
  treatment_course: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Medication {
  id: number;
  patient_id: number;
  admission_id: number;
  medication_name: string;
  dosage: string;
  frequency: string;
  route: string;
  start_date: string;
  end_date?: string;
  created_at: string;
}

export interface Vital {
  id: number;
  patient_id: number;
  admission_id: number;
  temperature: number;
  heart_rate: number;
  blood_pressure_systolic: number;
  blood_pressure_diastolic: number;
  oxygen_saturation: number;
  recorded_at: string;
}

export type DischargeReportStatus = 'draft' | 'generated' | 'under_review' | 'approved';

export interface DischargeReport {
  id: number;
  patient_id: number;
  admission_id: number;
  generated_content: string;
  edited_content?: string | null;
  effective_content: string;
  generation_provider: string;
  generation_model: string;
  status: DischargeReportStatus;
  approving_doctor_name?: string | null;
  approved_by?: number | null;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Hospital {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  specialties: string[];
  contact_number: string;
  created_at: string;
}

export interface HospitalCapacity {
  id: number;
  hospital_id: number;
  specialty: string;
  available_beds: number;
  total_beds: number;
  updated_at: string;
}

export type TransferStatus =
  | 'matching'
  | 'hospital_selected'
  | 'awaiting_acceptance'
  | 'accepted'
  | 'rejected'
  | 'ambulance_requested'
  | 'in_transit'
  | 'completed'
  | 'cancelled';

export interface HospitalMatch {
  hospital_id: number;
  hospital_name: string;
  required_specialty: string;
  available_beds: number;
  total_beds: number;
  distance_km: number;
  capacity_score: number;
  distance_score: number;
  match_score: number;
  match_reasons: string[];
  emergency: boolean;
  contact_number: string;
  is_recommended: boolean;
}

export interface Transfer {
  id: number;
  patient_id: number;
  admission_id: number;
  clinical_decision_id?: number;
  sending_hospital_id: number;
  receiving_hospital_id?: number;
  required_specialty: string;
  emergency: boolean;
  status: TransferStatus;
  requested_by?: number;
  requested_at: string;
  selected_hospital_at?: string;
  accepted_at?: string;
  rejected_at?: string;
  completed_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TransferSummary {
  id: number;
  patient_id: number;
  patient_name: string;
  patient_code: string;
  admission_id: number;
  primary_diagnosis: string;
  required_specialty: string;
  emergency: boolean;
  status: TransferStatus;
  sending_hospital_id: number;
  sending_hospital_name: string;
  receiving_hospital_id?: number;
  receiving_hospital_name?: string;
  requested_at: string;
  selected_hospital_at?: string;
}

export interface TransferDetail extends Transfer {
  patient_name: string;
  patient_code: string;
  date_of_birth?: string;
  gender?: string;
  primary_diagnosis: string;
  ward?: string;
  bed_number?: string;
  clinical_reason?: string;
  clinical_notes?: string;
  sending_hospital_name: string;
  sending_hospital_contact?: string;
  receiving_hospital_name?: string;
  receiving_hospital_contact?: string;
  receiving_hospital_available_beds?: number;
  receiving_hospital_distance_km?: number;
  requested_by_name?: string;
  packet_id?: number;
  packet_status?: TransferPacketStatus;
  rejection_reason?: string;
  acceptance_notes?: string;
  latest_decision?: TransferDecisionType;
  ambulance_dispatch_id?: number;
  ambulance_status?: AmbulanceStatus;
  ambulance_reference?: string;
  ambulance_vehicle?: string;
  ambulance_eta_minutes?: number;
}

export type TransferPacketStatus = 'prepared' | 'sent' | 'viewed';

export type TransferDecisionType = 'accepted' | 'rejected';

export interface MedicationPacket {
  medication_name: string;
  dosage: string;
  frequency: string;
  route: string;
  start_date: string;
  end_date?: string;
}

export interface VitalPacket {
  temperature: number;
  heart_rate: number;
  blood_pressure: string;
  oxygen_saturation: number;
  recorded_at: string;
}

export interface TransferPacketContent {
  transfer_id: number;
  patient_summary: {
    patient_id: number;
    patient_name: string;
    patient_code: string;
    date_of_birth?: string;
    gender?: string;
    blood_group?: string;
    phone?: string;
    emergency_contact?: string;
  };
  admission_summary: {
    admission_id: number;
    admission_date: string;
    ward?: string;
    bed_number?: string;
    status: string;
  };
  primary_diagnosis: string;
  transfer_reason: string;
  required_specialty: string;
  urgency: string;
  treatment_course: string;
  current_medications: MedicationPacket[];
  recent_vitals: VitalPacket[];
  clinical_notes?: string;
  approved_discharge_summary?: string;
  sending_hospital: {
    hospital_id: number;
    hospital_name: string;
    contact_number?: string;
  };
  sending_doctor: {
    doctor_id?: number;
    name: string;
    email?: string;
  };
  receiving_hospital: {
    hospital_id: number;
    hospital_name: string;
    contact_number?: string;
  };
}

export interface TransferPacket {
  id: number;
  transfer_id: number;
  patient_id: number;
  admission_id: number;
  packet_content: TransferPacketContent;
  status: TransferPacketStatus;
  prepared_at: string;
  sent_at?: string;
  viewed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface TransferDecision {
  id: number;
  transfer_id: number;
  hospital_id: number;
  hospital_name?: string;
  decision: TransferDecisionType;
  reason?: string;
  decided_by?: number;
  decided_by_name?: string;
  decided_at: string;
}

export type AmbulanceStatus =
  | 'requested'
  | 'en_route'
  | 'arrived_pickup'
  | 'patient_onboard'
  | 'in_transit'
  | 'arrived_destination'
  | 'completed'
  | 'cancelled';

export interface AmbulanceDispatch {
  id: number;
  transfer_id: number;
  dispatch_reference: string;
  status: AmbulanceStatus;
  pickup_name: string;
  pickup_latitude: number;
  pickup_longitude: number;
  destination_name: string;
  destination_latitude: number;
  destination_longitude: number;
  distance_km: number;
  estimated_duration_minutes: number;
  current_eta_minutes: number;
  vehicle_number?: string;
  driver_name?: string;
  driver_phone?: string;
  cancellation_reason?: string;
  requested_at: string;
  en_route_at?: string;
  arrived_pickup_at?: string;
  patient_onboard_at?: string;
  departed_pickup_at?: string;
  arrived_destination_at?: string;
  completed_at?: string;
  created_at?: string;
  updated_at?: string;
  patient_id?: number;
  patient_name?: string;
  patient_code?: string;
  primary_diagnosis?: string;
  required_specialty?: string;
  emergency?: boolean;
  transfer_status?: string;
}

export interface AmbulanceDashboardCounts {
  requested: number;
  en_route: number;
  at_pickup: number;
  in_transit: number;
  completed: number;
  total: number;
}

export type BillingStatus = 'pending' | 'processing' | 'cleared' | 'failed' | 'waived' | 'deferred';

export interface BillingClearance {
  id: number;
  patient_id: number;
  admission_id: number;
  transfer_id?: number | null;
  discharge_report_id?: number | null;
  status: BillingStatus;
  total_amount?: number | null;
  amount_paid?: number | null;
  outstanding_amount?: number | null;
  clearance_reference?: string | null;
  confirmed_by?: number | null;
  confirmed_at?: string | null;
  deferred: boolean;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  patient_name?: string | null;
  patient_code?: string | null;
  primary_diagnosis?: string | null;
  bed_number?: string | null;
  ward?: string | null;
  confirmed_by_name?: string | null;
  report_status?: string | null;
  transfer_status?: string | null;
}

export type EventDeliveryStatus = 'pending' | 'delivered' | 'failed';
export type EventOrchestrationStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface WorkflowEvent {
  id: number;
  event_type: string;
  entity_type: string;
  entity_id: number;
  payload: Record<string, unknown>;
  status: string;
  delivery_status: EventDeliveryStatus;
  orchestration_status: EventOrchestrationStatus;
  attempt_count: number;
  last_attempt_at?: string | null;
  delivered_at?: string | null;
  last_error?: string | null;
  trusted_provenance: boolean;
  created_at: string;
}

export interface WorkflowDashboardCounts {
  total_events: number;
  delivery_pending: number;
  delivery_delivered: number;
  delivery_failed: number;
  orchestration_pending: number;
  orchestration_processing: number;
  orchestration_completed: number;
  orchestration_failed: number;
}

export interface WorkflowEventRetryResponse {
  event_id: number;
  delivery_status: string;
  attempt_count: number;
  message: string;
}

export type ClinicalDecisionType = 'discharge' | 'transfer';
export type TransferUrgency = 'emergency' | 'non_emergency';
export type ClinicalDecisionStatus = 'draft' | 'confirmed' | 'cancelled';

export interface ClinicalDecisionRequest {
  decision_type: ClinicalDecisionType;
  transfer_urgency?: TransferUrgency;
  reason: string;
  required_specialty?: string;
  notes?: string;
}

export interface ClinicalDecision extends ClinicalDecisionRequest {
  id: number;
  patient_id: number;
  admission_id: number;
  decided_by: number;
  decided_by_name: string;
  decided_at?: string;
  status: ClinicalDecisionStatus;
  created_at: string;
  updated_at: string;
}

export interface HealthStatusResponse {
  status: string;
  service: string;
}
