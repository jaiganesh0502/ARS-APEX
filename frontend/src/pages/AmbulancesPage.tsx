import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Ambulance,
  Clock,
  MapPin,
  ShieldAlert,
  ArrowRight,
  RefreshCw,
  FlaskConical,
  CheckCircle2,
  Navigation,
  UserCheck,
} from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { Spinner } from '../components/common/Spinner';
import { ambulanceApi } from '../api/ambulance';
import { AmbulanceDashboardCounts, AmbulanceDispatch } from '../types';

export const AmbulancesPage: React.FC = () => {
  const navigate = useNavigate();

  const [dispatches, setDispatches] = useState<AmbulanceDispatch[]>([]);
  const [counts, setCounts] = useState<AmbulanceDashboardCounts | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | 'active' | 'completed' | 'emergency'>('all');

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const countsData = await ambulanceApi.getDashboardCounts();
      setCounts(countsData);

      const params: { status?: string; emergency?: boolean } = {};
      if (activeTab === 'completed') params.status = 'completed';
      if (activeTab === 'emergency') params.emergency = true;

      const listData = await ambulanceApi.listDispatches(params);
      if (activeTab === 'active') {
        const activeStatuses = ['requested', 'en_route', 'arrived_pickup', 'patient_onboard', 'in_transit'];
        setDispatches(listData.filter((d) => activeStatuses.includes(d.status)));
      } else {
        setDispatches(listData);
      }
    } catch (err) {
      console.error('Failed to fetch ambulance dispatches', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <PageHeader
          title="Ambulance Dispatch & Fleet Tracking"
          description="Monitor simulated emergency transit telemetry, vehicle assignments, and destination arrival ETAs."
          action={
            <span className="flex items-center gap-1.5 text-xs font-semibold text-blue-700 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-200 shadow-sm">
              <FlaskConical className="w-4 h-4 text-blue-600" />
              Simulated Fleet Mode
            </span>
          }
        />
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />}
          onClick={fetchData}
        >
          Refresh Fleet
        </Button>
      </div>

      {/* KPI Metric Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">Total Active</span>
          <span className="text-xl font-extrabold text-slate-900 mt-1 block">
            {counts ? counts.total : 0}
          </span>
        </div>

        <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block flex items-center gap-1">
            <Clock className="w-3 h-3 text-amber-500" /> Requested
          </span>
          <span className="text-xl font-extrabold text-amber-600 mt-1 block">
            {counts ? counts.requested : 0}
          </span>
        </div>

        <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block flex items-center gap-1">
            <Ambulance className="w-3 h-3 text-blue-600" /> En Route
          </span>
          <span className="text-xl font-extrabold text-blue-700 mt-1 block">
            {counts ? counts.en_route : 0}
          </span>
        </div>

        <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block flex items-center gap-1">
            <UserCheck className="w-3 h-3 text-indigo-600" /> At Pickup
          </span>
          <span className="text-xl font-extrabold text-indigo-700 mt-1 block">
            {counts ? counts.at_pickup : 0}
          </span>
        </div>

        <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block flex items-center gap-1">
            <Navigation className="w-3 h-3 text-purple-600" /> In Transit
          </span>
          <span className="text-xl font-extrabold text-purple-700 mt-1 block">
            {counts ? counts.in_transit : 0}
          </span>
        </div>

        <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Completed
          </span>
          <span className="text-xl font-extrabold text-emerald-700 mt-1 block">
            {counts ? counts.completed : 0}
          </span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'all'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          All Dispatches
        </button>
        <button
          onClick={() => setActiveTab('active')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'active'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Active Transit
        </button>
        <button
          onClick={() => setActiveTab('completed')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'completed'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Completed
        </button>
        <button
          onClick={() => setActiveTab('emergency')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
            activeTab === 'emergency'
              ? 'bg-rose-600 text-white shadow-sm'
              : 'text-rose-700 bg-rose-50 hover:bg-rose-100'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" /> Emergency Priority
        </button>
      </div>

      {/* Dispatch Fleet Table */}
      <Card>
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center">
            <Spinner size="md" />
            <span className="text-xs text-slate-500 mt-2">Loading ambulance telemetry...</span>
          </div>
        ) : dispatches.length === 0 ? (
          <div className="py-16 text-center">
            <Ambulance className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h4 className="text-sm font-semibold text-slate-700">No ambulance dispatches found</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Active ambulance dispatches for accepted transfer cases will appear here for fleet tracking.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Dispatch Reference</th>
                  <th className="px-4 py-3">Patient</th>
                  <th className="px-4 py-3">Transit Route</th>
                  <th className="px-4 py-3">Urgency</th>
                  <th className="px-4 py-3">Vehicle</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Simulated ETA</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {dispatches.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="px-4 py-3.5 font-mono text-xs font-semibold text-blue-700">
                      {d.dispatch_reference}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="font-semibold text-slate-900">{d.patient_name}</div>
                      <span className="text-[11px] font-mono text-slate-400">{d.patient_code}</span>
                    </td>
                    <td className="px-4 py-3.5 text-xs">
                      <div className="flex items-center gap-1 text-slate-700 font-medium truncate max-w-[200px]">
                        <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                        <span>{d.pickup_name}</span>
                      </div>
                      <div className="flex items-center gap-1 text-blue-700 text-[11px] truncate max-w-[200px] mt-0.5">
                        <ArrowRight className="w-3 h-3 text-slate-400 shrink-0" />
                        <span>{d.destination_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      {d.emergency ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200 rounded">
                          <ShieldAlert className="w-3 h-3" /> EMERGENCY
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500 font-medium">Standard</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-xs font-mono text-slate-600">
                      {d.vehicle_number || 'TN-DEMO-101'}
                    </td>
                    <td className="px-4 py-3.5">
                      <StatusBadge status={d.status} />
                    </td>
                    <td className="px-4 py-3.5 text-xs font-semibold">
                      {d.status === 'completed' ? (
                        <span className="text-emerald-700 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Arrived
                        </span>
                      ) : d.status === 'cancelled' ? (
                        <span className="text-slate-400">Cancelled</span>
                      ) : (
                        <span className="text-blue-700 flex items-center gap-1 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 w-fit">
                          <Clock className="w-3.5 h-3.5" /> {d.current_eta_minutes} mins
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <Button
                        variant="primary"
                        size="sm"
                        rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                        onClick={() => navigate(`/ambulances/${d.id}`)}
                      >
                        Track Dispatch
                      </Button>
                    </td>
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
