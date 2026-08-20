import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, ArrowRight, Building2, RefreshCw, Inbox } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { Spinner } from '../components/common/Spinner';
import { transferApi } from '../api/transfers';
import { TransferStatus, TransferSummary } from '../types';

export const IncomingTransfersPage: React.FC = () => {
  const navigate = useNavigate();

  const [transfers, setTransfers] = useState<TransferSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | 'awaiting_acceptance' | 'accepted' | 'emergency'>('awaiting_acceptance');

  const fetchTransfers = async () => {
    setIsLoading(true);
    try {
      const params: { status?: string; emergency?: boolean } = {};
      if (activeTab === 'awaiting_acceptance') params.status = 'awaiting_acceptance';
      if (activeTab === 'accepted') params.status = 'accepted';
      if (activeTab === 'emergency') params.emergency = true;

      const data = await transferApi.getIncomingTransfers(params);
      setTransfers(data);
    } catch (err) {
      console.error('Failed to fetch incoming transfers', err);
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
          title="Incoming Transfers"
          description="Receiving facility triage inbox: review clinical transfer packets, verify capacity, and record acceptance decisions."
        />
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />}
          onClick={fetchTransfers}
        >
          Refresh Queue
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('awaiting_acceptance')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'awaiting_acceptance'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Awaiting Review
        </button>
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'all'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          All Requests
        </button>
        <button
          onClick={() => setActiveTab('accepted')}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === 'accepted'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          Accepted Cases
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

      <Card>
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center">
            <Spinner size="md" />
            <span className="text-xs text-slate-500 mt-2">Loading incoming transfer requests...</span>
          </div>
        ) : transfers.length === 0 ? (
          <div className="py-16 text-center">
            <Inbox className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h4 className="text-sm font-semibold text-slate-700">No incoming transfers found</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              New transfer requests directed to this facility will appear here for physician clinical review and acceptance.
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
                  <th className="px-4 py-3">Origin Facility</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transfers.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="px-4 py-3.5 font-mono text-xs font-semibold text-blue-700">
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
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200 rounded">
                          <ShieldAlert className="w-3 h-3" /> EMERGENCY
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500 font-medium">Standard</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-xs">
                      <span className="font-medium text-slate-700 flex items-center gap-1">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        {t.sending_hospital_name}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <StatusBadge status={t.status as TransferStatus} />
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <Button
                        variant={t.status === 'awaiting_acceptance' ? 'primary' : 'outline'}
                        size="sm"
                        rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                        onClick={() => navigate(`/receiving/transfers/${t.id}`)}
                      >
                        Review Case
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
