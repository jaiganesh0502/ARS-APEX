import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { AmbulanceTimeline } from './AmbulanceTimeline';
import { AmbulanceControls } from './AmbulanceControls';
import { AmbulanceCancelModal } from './AmbulanceCancelModal';
import { AmbulanceDispatch } from '../../types';

const mockDispatch: AmbulanceDispatch = {
  id: 1,
  transfer_id: 10,
  dispatch_reference: 'AMB-20260820-0010',
  status: 'en_route',
  pickup_name: 'Metro Multispeciality Medical Center',
  pickup_latitude: 13.0827,
  pickup_longitude: 80.2707,
  destination_name: 'City Heart & Neuro Institute',
  destination_latitude: 13.04,
  destination_longitude: 80.25,
  distance_km: 5.3,
  estimated_duration_minutes: 13,
  current_eta_minutes: 11,
  vehicle_number: 'TN-DEMO-101 (Synthetic)',
  driver_name: 'Rajesh Sharma',
  driver_phone: '+91-98765-00101',
  requested_at: '2026-08-20T08:00:00Z',
  en_route_at: '2026-08-20T08:02:00Z',
  created_at: '2026-08-20T08:00:00Z',
  updated_at: '2026-08-20T08:02:00Z',
  patient_name: 'Meera Nair',
  patient_code: 'PT-1004',
  primary_diagnosis: 'Acute Ischemic Stroke',
  required_specialty: 'Neurology',
  emergency: true,
  transfer_status: 'ambulance_requested',
};

describe('AmbulanceTimeline presentation', () => {
  it('renders all transit milestones and vehicle reference', () => {
    const markup = renderToStaticMarkup(<AmbulanceTimeline dispatch={mockDispatch} />);

    expect(markup).toContain('Dispatch Requested');
    expect(markup).toContain('TN-DEMO-101');
    expect(markup).toContain('Ambulance En Route');
    expect(markup).toContain('Arrived at Sending Hospital');
    expect(markup).toContain('Metro Multispeciality Medical Center');
    expect(markup).toContain('Patient Onboard');
    expect(markup).toContain('Patient In Transit');
    expect(markup).toContain('City Heart &amp; Neuro Institute');
  });
});

describe('AmbulanceControls presentation', () => {
  it('renders simulation banner and current milestone advance trigger', () => {
    const markup = renderToStaticMarkup(
      <AmbulanceControls
        dispatch={mockDispatch}
        isLoading={false}
        onAdvanceStatus={() => {}}
        onRequestCancel={() => {}}
      />
    );

    expect(markup).toContain('MVP Simulation Mode');
    expect(markup).toContain('EN ROUTE');
    expect(markup).toContain('Mark Arrived at Sending Hospital');
    expect(markup).toContain('Cancel Dispatch');
  });
});

describe('AmbulanceCancelModal presentation', () => {
  it('renders cancellation modal with dispatch reference', () => {
    const markup = renderToStaticMarkup(
      <AmbulanceCancelModal
        isOpen={true}
        dispatchReference="AMB-20260820-0010"
        patientName="Meera Nair"
        isLoading={false}
        onClose={() => {}}
        onConfirm={() => {}}
      />
    );

    expect(markup).toContain('Cancel Ambulance Dispatch');
    expect(markup).toContain('AMB-20260820-0010');
    expect(markup).toContain('Meera Nair');
    expect(markup).toContain('Reason for Cancellation');
    expect(markup).toContain('Confirm Cancellation');
  });

  it('renders nothing when closed', () => {
    const markup = renderToStaticMarkup(
      <AmbulanceCancelModal
        isOpen={false}
        dispatchReference="AMB-20260820-0010"
        isLoading={false}
        onClose={() => {}}
        onConfirm={() => {}}
      />
    );
    expect(markup).toBe('');
  });
});
