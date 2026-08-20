import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { HospitalMatchCard } from './HospitalMatchCard';
import { HospitalSelectionModal } from './HospitalSelectionModal';
import { HospitalMatch } from '../../types';

const mockMatch: HospitalMatch = {
  hospital_id: 3,
  hospital_name: 'City Heart & Neuro Institute',
  required_specialty: 'Cardiology',
  available_beds: 3,
  total_beds: 12,
  distance_km: 2.4,
  capacity_score: 30,
  distance_score: 50,
  match_score: 80,
  match_reasons: [
    'Cardiology services available',
    '3 beds currently available',
    'Immediate local transit zone (2.4 km away)',
  ],
  emergency: false,
  contact_number: '+1-415-555-0302',
  is_recommended: true,
};

describe('HospitalMatchCard presentation', () => {
  it('renders hospital matching details, score, and reasons', () => {
    const markup = renderToStaticMarkup(
      <HospitalMatchCard match={mockMatch} onSelect={() => {}} />
    );

    expect(markup).toContain('City Heart &amp; Neuro Institute');
    expect(markup).toContain('80');
    expect(markup).toContain('3 beds free');
    expect(markup).toContain('2.4 km');
    expect(markup).toContain('RECOMMENDED');
    expect(markup).toContain('Cardiology services available');
  });

  it('renders selected badge when isSelected is true', () => {
    const markup = renderToStaticMarkup(
      <HospitalMatchCard match={mockMatch} isSelected={true} onSelect={() => {}} />
    );
    expect(markup).toContain('SELECTED FACILITY');
  });
});

describe('HospitalSelectionModal presentation', () => {
  it('renders confirmation modal with facility details', () => {
    const markup = renderToStaticMarkup(
      <HospitalSelectionModal
        isOpen={true}
        match={mockMatch}
        isLoading={false}
        onClose={() => {}}
        onConfirm={() => {}}
      />
    );

    expect(markup).toContain('Select receiving hospital?');
    expect(markup).toContain('City Heart &amp; Neuro Institute');
    expect(markup).toContain('3 of 12 beds free');
    expect(markup).toContain('2.4 km');
    expect(markup).toContain('Confirm Selection');
  });

  it('does not render when closed', () => {
    const markup = renderToStaticMarkup(
      <HospitalSelectionModal
        isOpen={false}
        match={mockMatch}
        isLoading={false}
        onClose={() => {}}
        onConfirm={() => {}}
      />
    );
    expect(markup).toBe('');
  });
});
