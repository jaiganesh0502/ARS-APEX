import React, { useCallback, useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { getPatients } from '../api/patients';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { PageHeader } from '../components/common/PageHeader';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/StatusBadge';
import { AdmissionStatus, PatientListResponse } from '../types';

type StatusFilter = AdmissionStatus | '';

export const PatientsPage: React.FC = () => {
  const navigate = useNavigate();
  const [result, setResult] = useState<PatientListResponse>({ items: [], page: 1, page_size: 20, total: 0 });
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StatusFilter>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setResult(await getPatients({ page: 1, pageSize: 20, search, status }));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [search, status, reloadKey]);

  useEffect(() => {
    const timer = window.setTimeout(loadPatients, 250);
    return () => window.clearTimeout(timer);
  }, [loadPatients]);

  return (
    <div className="space-y-6">
      <PageHeader title="Patients" description="Review active patient records and admission context." />

      <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[1fr_220px_auto] md:items-center">
        <label className="flex items-center gap-3 rounded-md border border-slate-300 px-3 py-2 focus-within:border-primary-600 focus-within:ring-1 focus-within:ring-primary-600">
          <Search className="h-4 w-4 shrink-0 text-slate-400" />
          <span className="sr-only">Search patient</span>
          <input className="w-full bg-transparent text-sm outline-none" placeholder="Search patient code or name" value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label>
          <span className="sr-only">Admission status</span>
          <select className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700" value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}>
            <option value="">All statuses</option>
            <option value="admitted">Admitted</option>
            <option value="discharging">Discharging</option>
            <option value="transfer_pending">Transfer Pending</option>
            <option value="transferred">Transferred</option>
            <option value="discharged">Discharged</option>
          </select>
        </label>
        <div className="text-sm font-medium text-slate-600">{result.total} patients</div>
      </div>

      <Card>
        {loading ? (
          <div className="flex min-h-56 flex-col items-center justify-center gap-3 text-sm text-slate-500"><Spinner size="lg" /><span>Loading patients…</span></div>
        ) : error ? (
          <div className="flex min-h-56 flex-col items-center justify-center gap-3 text-center">
            <p className="font-medium text-slate-800">Patient records could not be loaded.</p>
            <p className="text-sm text-slate-500">Check the connection and try again.</p>
            <Button variant="outline" onClick={() => setReloadKey((value) => value + 1)}>Retry</Button>
          </div>
        ) : result.items.length === 0 ? (
          <div className="min-h-56 content-center text-center text-sm text-slate-500">No patients found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm text-slate-700">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Patient ID</th><th className="px-4 py-3">Patient Name</th><th className="px-4 py-3">Age / Gender</th><th className="px-4 py-3">Diagnosis</th><th className="px-4 py-3">Ward / Bed</th><th className="px-4 py-3">Admission Status</th><th className="px-4 py-3 text-right">Action</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {result.items.map((patient) => (
                  <tr key={patient.id} className="hover:bg-slate-50">
                    <td className="px-4 py-4 font-mono text-xs font-semibold text-primary-700">{patient.patient_code}</td>
                    <td className="px-4 py-4 font-medium text-slate-900">{patient.first_name} {patient.last_name}</td>
                    <td className="px-4 py-4">{patient.age} / {patient.gender}</td>
                    <td className="px-4 py-4">{patient.primary_diagnosis || 'Not recorded'}</td>
                    <td className="px-4 py-4">{patient.ward ? `${patient.ward} / ${patient.bed_number || 'Unassigned'}` : 'Unassigned'}</td>
                    <td className="px-4 py-4">{patient.admission_status ? <StatusBadge status={patient.admission_status} /> : <span>Not admitted</span>}</td>
                    <td className="px-4 py-4 text-right"><Button variant="outline" size="sm" onClick={() => navigate(`/patients/${patient.id}`)}>View Patient</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
