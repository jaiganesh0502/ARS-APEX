import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BedDouble, Search } from 'lucide-react';
import { Link } from 'react-router-dom';

import { listAllBeds } from '../api/beds';
import { MetricCard } from '../components/common/MetricCard';
import { PageHeader } from '../components/common/PageHeader';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/StatusBadge';
import { filterBeds, summarizeBeds } from '../features/beds/bedState';
import type { BedFilters, BedStatus, BedSummary } from '../types';

const statusOptions: Array<{ value: BedStatus; label: string }> = [
  { value: 'occupied', label: 'Occupied' },
  { value: 'vacating', label: 'Vacating' },
  { value: 'cleaning', label: 'Cleaning' },
  { value: 'available', label: 'Available' },
  { value: 'reserved', label: 'Reserved' },
];

export const loadBedsPageData = (): Promise<BedSummary[]> => listAllBeds();

const formatDateTime = (value: string) => new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
}).format(new Date(value));

export const BedsSummaryCards: React.FC<{
  beds: BedSummary[];
  state?: 'loading' | 'ready' | 'error';
}> = ({ beds, state = 'ready' }) => {
  const counts = summarizeBeds(beds);
  const cards = [
    ['Total Beds', counts.total],
    ['Occupied', counts.occupied],
    ['Vacating', counts.vacating],
    ['Cleaning', counts.cleaning],
    ['Available', counts.available],
    ['Reserved', counts.reserved],
  ] as const;

  return <section aria-label="Bed status summary" aria-busy={state === 'loading'} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
    {state !== 'ready' && <p className="sr-only">{state === 'loading' ? 'Loading bed counts' : 'Bed counts unavailable'}</p>}
    {cards.map(([label, value]) => <MetricCard key={label} label={label} value={state === 'ready' ? value : '—'} icon={<BedDouble className="h-4 w-4" aria-hidden="true" />} />)}
  </section>;
};

export const BedsTable: React.FC<{ beds: BedSummary[]; emptyMessage?: string }> = ({
  beds,
  emptyMessage = 'No beds match the selected filters.',
}) => <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
  <div className="overflow-x-auto">
    <table className="w-full min-w-[1080px] text-left text-sm">
      <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
        <tr>
          {['Ward', 'Bed', 'Status', 'Current Patient', 'Patient ID', 'Diagnosis', 'Last Updated', 'Action'].map((header) => <th key={header} scope="col" className="px-4 py-3">{header}</th>)}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {beds.map((bed) => {
          const isAvailable = bed.status === 'available';
          return <tr key={bed.id} className="text-slate-700 hover:bg-slate-50">
            <td className="px-4 py-4 font-medium text-slate-900">{bed.ward}</td>
            <td className="px-4 py-4 font-semibold text-slate-900">{bed.bed_number}</td>
            <td className="px-4 py-4"><StatusBadge status={bed.status} /></td>
            <td className="px-4 py-4">
              {isAvailable
                ? <span className="flex flex-col"><span aria-label="No current patient">—</span><span className="text-xs text-green-700">Ready for assignment</span></span>
                : (bed.patient_name || '—')}
            </td>
            <td className="px-4 py-4">{bed.patient_code || '—'}</td>
            <td className="max-w-xs px-4 py-4">{bed.primary_diagnosis || '—'}</td>
            <td className="whitespace-nowrap px-4 py-4 text-slate-500">{formatDateTime(bed.updated_at)}</td>
            <td className="px-4 py-4"><Link className="font-semibold text-primary-700 hover:text-primary-900 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2" to={`/beds/${bed.id}`}>View Details</Link></td>
          </tr>;
        })}
        {beds.length === 0 && <tr><td colSpan={8} className="px-4 py-12 text-center text-slate-500">{emptyMessage}</td></tr>}
      </tbody>
    </table>
  </div>
</div>;

export const BedsPage: React.FC = () => {
  const [beds, setBeds] = useState<BedSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [ward, setWard] = useState('');
  const [status, setStatus] = useState<BedStatus | ''>('');
  const [search, setSearch] = useState('');
  const loadEpochRef = useRef(0);

  useEffect(() => {
    const epoch = loadEpochRef.current + 1;
    loadEpochRef.current = epoch;
    setLoading(true);
    setError('');

    void loadBedsPageData()
      .then((loadedBeds) => {
        if (loadEpochRef.current === epoch) setBeds(loadedBeds);
      })
      .catch(() => {
        if (loadEpochRef.current === epoch) setError('Bed information could not be loaded. Please try again.');
      })
      .finally(() => {
        if (loadEpochRef.current === epoch) setLoading(false);
      });

    return () => {
      if (loadEpochRef.current === epoch) loadEpochRef.current += 1;
    };
  }, [reloadKey]);

  const wards = useMemo(() => [...new Set(beds.map((bed) => bed.ward))].sort((a, b) => a.localeCompare(b)), [beds]);
  const activeFilters: BedFilters = {
    ...(ward ? { ward } : {}),
    ...(status ? { status } : {}),
    ...(search ? { search } : {}),
  };
  const visibleBeds = filterBeds(beds, activeFilters);

  return <div className="space-y-6">
    <PageHeader title="Bed Management" description="Monitor bed occupancy and guide each bed safely through release and cleaning." />
    <BedsSummaryCards beds={beds} state={error ? 'error' : loading ? 'loading' : 'ready'} />

    <section aria-label="Bed filters" className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[1fr_1fr_2fr]">
      <label className="text-sm font-medium text-slate-700">Ward
        <select className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-600/20" value={ward} onChange={(event) => setWard(event.target.value)}>
          <option value="">All wards</option>
          {wards.map((wardName) => <option key={wardName} value={wardName}>{wardName}</option>)}
        </select>
      </label>
      <label className="text-sm font-medium text-slate-700">Status
        <select className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-600/20" value={status} onChange={(event) => setStatus(event.target.value as BedStatus | '')}>
          <option value="">All statuses</option>
          {statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <label className="text-sm font-medium text-slate-700">Search
        <span className="relative mt-1 block"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" /><input className="block w-full rounded-md border border-slate-300 py-2 pl-9 pr-3 text-slate-900 placeholder:text-slate-400 focus:border-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-600/20" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Bed number, patient name, or patient ID" /></span>
      </label>
    </section>

    {error
      ? <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center" role="alert"><p className="font-medium text-red-900">{error}</p><button className="mt-4 rounded-md bg-primary-700 px-4 py-2 text-sm font-medium text-white hover:bg-primary-800 focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2" onClick={() => setReloadKey((value) => value + 1)}>Retry</button></div>
      : loading
        ? <div className="flex min-h-56 flex-col items-center justify-center gap-3 text-sm text-slate-500"><Spinner size="lg" /><span>Loading bed information…</span></div>
        : <BedsTable beds={visibleBeds} emptyMessage={beds.length === 0 ? 'No beds are currently available to display.' : undefined} />}
  </div>;
};
