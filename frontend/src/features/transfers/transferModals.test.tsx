import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { TransferPacketModal } from './TransferPacketModal';
import { TransferAcceptModal } from './TransferAcceptModal';
import { TransferRejectModal } from './TransferRejectModal';
import { TransferPacket } from '../../types';

const mockPacket: TransferPacket = {
  id: 1,
  transfer_id: 10,
  patient_id: 4,
  admission_id: 4,
  packet_content: {
    transfer_id: 10,
    patient_summary: {
      patient_id: 4,
      patient_name: 'Meera Nair',
      patient_code: 'PT-1004',
      date_of_birth: '1982-03-15',
      gender: 'Female',
      blood_group: 'B+',
      phone: '+91-9876543210',
      emergency_contact: '+91-9876543211',
    },
    admission_summary: {
      admission_id: 4,
      admission_date: '2026-08-19T08:00:00Z',
      ward: 'Neurology Ward',
      bed_number: 'NEU-04',
      status: 'transfer_pending',
    },
    primary_diagnosis: 'Acute Ischemic Stroke',
    transfer_reason: 'Requires comprehensive stroke center for endovascular thrombectomy.',
    required_specialty: 'Neurology',
    urgency: 'emergency',
    treatment_course: 'Thrombolytic protocol initiated.',
    current_medications: [
      {
        medication_name: 'Alteplase',
        dosage: '0.9mg/kg',
        frequency: 'Stat IV',
        route: 'Intravenous',
        start_date: '2026-08-19',
      },
    ],
    recent_vitals: [
      {
        temperature: 36.9,
        heart_rate: 82,
        blood_pressure: '140/90 mmHg',
        oxygen_saturation: 97,
        recorded_at: '2026-08-19T09:30:00Z',
      },
    ],
    clinical_notes: 'NIHSS Score 14 on admission.',
    sending_hospital: {
      hospital_id: 1,
      hospital_name: 'Metro Multispeciality Medical Center',
      contact_number: '+1-415-555-0100',
    },
    sending_doctor: {
      doctor_id: 1,
      name: 'Dr. Asha Rao',
      email: 'asha.rao@metrohospital.org',
    },
    receiving_hospital: {
      hospital_id: 3,
      hospital_name: 'City Heart & Neuro Institute',
      contact_number: '+1-415-555-0200',
    },
  },
  status: 'sent',
  prepared_at: '2026-08-19T09:40:00Z',
  sent_at: '2026-08-19T09:42:00Z',
  created_at: '2026-08-19T09:40:00Z',
  updated_at: '2026-08-19T09:42:00Z',
};

describe('TransferPacketModal presentation', () => {
  it('renders clinical packet snapshot with patient and treatment details', () => {
    const markup = renderToStaticMarkup(
      <TransferPacketModal isOpen={true} packet={mockPacket} onClose={() => {}} />
    );

    expect(markup).toContain('Clinical Transfer Packet');
    expect(markup).toContain('Meera Nair');
    expect(markup).toContain('PT-1004');
    expect(markup).toContain('Acute Ischemic Stroke');
    expect(markup).toContain('Alteplase');
    expect(markup).toContain('140/90 mmHg');
    expect(markup).toContain('City Heart &amp; Neuro Institute');
    expect(markup).toContain('SENT');
  });

  it('renders nothing when closed', () => {
    const markup = renderToStaticMarkup(
      <TransferPacketModal isOpen={false} packet={mockPacket} onClose={() => {}} />
    );
    expect(markup).toBe('');
  });
});

describe('TransferAcceptModal presentation', () => {
  it('renders capacity reservation notice and confirmation action', () => {
    const markup = renderToStaticMarkup(
      <TransferAcceptModal
        isOpen={true}
        patientName="Meera Nair"
        specialty="Neurology"
        availableBeds={2}
        isLoading={false}
        onClose={() => {}}
        onConfirm={() => {}}
      />
    );

    expect(markup).toContain('Accept Transfer &amp; Reserve Bed');
    expect(markup).toContain('Meera Nair');
    expect(markup).toContain('Neurology');
    expect(markup).toContain('2 beds free');
    expect(markup).toContain('Confirm Acceptance &amp; Reserve Bed');
  });
});

describe('TransferRejectModal presentation', () => {
  it('renders rejection justification modal with origin facility', () => {
    const markup = renderToStaticMarkup(
      <TransferRejectModal
        isOpen={true}
        patientName="Meera Nair"
        specialty="Neurology"
        sendingHospitalName="Metro Multispeciality Medical Center"
        isLoading={false}
        onClose={() => {}}
        onConfirm={() => {}}
      />
    );

    expect(markup).toContain('Reject Transfer Request');
    expect(markup).toContain('Meera Nair');
    expect(markup).toContain('Reason for Rejection');
    expect(markup).toContain('Confirm Rejection');
  });
});
