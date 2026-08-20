import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, ArrowRight, Building2, RefreshCw } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { Spinner } from '../components/common/Spinner';
import { transferApi } from '../api/transfers';
import { TransferStatus, TransferSummary } from '../types';

export const TransfersPage: React.FC = () => {
  const navigate = useNavigate();

  const [transfers, setTransfers] = useState<TransferSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | 'matching' | 'awaiting_acceptance' | 'emergency'>('all');

  const fetchTransfers = async () => {
    setIsLoading(true);
    try {
      const params: { status?: string; emergency?: boolean } = {};
      if (activeTab === 'matching') params.status = 'matching';
      if (activeTab === 'awaiting_acceptance') params.status = 'awaiting_acceptance';
      if (activeTab === 'emergency') params.emergency = true;

      const data = await transferApi.getTransfers(params);
      setTransfers(data);
    } catch (err) {
      console.error('Failed to fetch transfers', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTransfers();
  }, [activeTab]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader
          title="Inter-Hospital Transfer Operations"
          description="Match specialized tertiary facilities, coordinate physician handoffs, and track transport telemetry."
        />
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />}
          onClick={fetchTransfers}
        >
          Refresh
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'all'
              ? 'bg-primary-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          All Transfers
        </button>
        <button
          onClick={() => setActiveTab('matching')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'matching'
              ? 'bg-primary-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Matching In Progress
        </button>
        <button
          onClick={() => setActiveTab('awaiting_acceptance')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'awaiting_acceptance'
              ? 'bg-primary-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Awaiting Acceptance
        </button>
        <button
          onClick={() => setActiveTab('emergency')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
            activeTab === 'emergency'
              ? 'bg-red-600 text-white shadow-sm'
              : 'text-red-700 bg-red-50 hover:bg-red-100'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" /> Emergency Priority
        </button>
      </div>

      <Card>
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center">
            <Spinner size="md" />
            <span className="text-xs text-slate-500 mt-2">Loading active transfer cases...</span>
          </div>
        ) : transfers.length === 0 ? (
          <div className="py-16 text-center">
            <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h4 className="text-sm font-semibold text-slate-700">No transfer cases found</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Transfer cases are automatically initialized when attending doctors confirm an inter-hospital transfer decision.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Transfer ID</th>
                  <th className="px-4 py-3">Patient</th>
                  <th className="px-4 py-3">Primary Diagnosis</th>
                  <th className="px-4 py-3">Required Specialty</th>
                  <th className="px-4 py-3">Urgency</th>
                  <th className="px-4 py-3">Receiving Hospital</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transfers.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="px-4 py-3.5 font-mono text-xs font-semibold text-primary-700">
                      #TRF-00{t.id}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="font-semibold text-slate-900">{t.patient_name}</div>
                      <span className="text-[11px] font-mono text-slate-400">{t.patient_code}</span>
                    </td>
                    <td className="px-4 py-3.5 text-xs text-slate-600 max-w-[180px] truncate">
                      {t.primary_diagnosis}
                    </td>
                    <td className="px-4 py-3.5 text-slate-800 font-medium text-xs">
                      {t.required_specialty}
                    </td>
                    <td className="px-4 py-3.5">
                      {t.emergency ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold bg-red-50 text-red-700 border border-red-200 rounded">
                          <ShieldAlert className="w-3 h-3" /> EMERGENCY
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500 font-medium">Standard</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-xs">
                      {t.receiving_hospital_name ? (
                        <span className="font-semibold text-slate-800 flex items-center gap-1">
                          <Building2 className="w-3.5 h-3.5 text-slate-400" />
                          {t.receiving_hospital_name}
                        </span>
                      ) : (
                        <span className="text-amber-600 font-medium italic">
                          Matching in Progress...
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3.5">
                      <StatusBadge status={t.status as TransferStatus} />
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                        onClick={() => navigate(`/transfers/${t.id}`)}
                      >
                        View Transfer
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
