import type { BedAction, BedCounts, BedFilters, BedSummary } from '../../types';

export const summarizeBeds = (beds: BedSummary[]): BedCounts => {
  const counts: BedCounts = {
    total: beds.length,
    occupied: 0,
    vacating: 0,
    cleaning: 0,
    available: 0,
    reserved: 0,
  };

  for (const bed of beds) {
    counts[bed.status] += 1;
  }

  return counts;
};

export const filterBeds = (beds: BedSummary[], filters: BedFilters): BedSummary[] => {
  const search = filters.search?.toLocaleLowerCase() ?? '';

  return beds.filter((bed) => {
    if (filters.ward !== undefined && bed.ward !== filters.ward) return false;
    if (filters.status !== undefined && bed.status !== filters.status) return false;
    if (search === '') return true;

    return [bed.bed_number, bed.patient_name ?? '', bed.patient_code ?? '']
      .some((value) => value.toLocaleLowerCase().includes(search));
  });
};

export const bedAction = (bed: BedSummary): BedAction | undefined => {
  if (bed.status === 'occupied') return bed.release_eligible ? 'start_release' : undefined;
  if (bed.status === 'vacating') return 'patient_departed';
  if (bed.status === 'cleaning') return 'cleaning_complete';
  return undefined;
};
