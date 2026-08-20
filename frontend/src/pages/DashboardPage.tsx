import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  FileCheck2,
  ArrowRightLeft,
  BedDouble,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { MetricCard } from '../components/common/MetricCard';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import { listAllBeds } from '../api/beds';
import { summarizeBeds } from '../features/beds/bedState';
import type { BedSummary } from '../types';

type BedMetricState = 'loading' | 'ready' | 'error';

export const DashboardBedMetric: React.FC<{ beds: BedSummary[]; state: BedMetricState }> = ({ beds, state }) => {
  if (state === 'loading') {
    return <div aria-busy="true"><MetricCard label="Bed Occupancy" value="—" change="Loading bed data" icon={<BedDouble className="w-4 h-4" />} /></div>;
  }
  if (state === 'error') {
    return <div><MetricCard label="Bed Occupancy" value="—" change="Bed data unavailable" icon={<BedDouble className="w-4 h-4" />} /></div>;
  }

  const counts = summarizeBeds(beds);
  const occupancy = counts.total === 0 ? 0 : Math.round(((counts.occupied + counts.vacating) / counts.total) * 100);
  return <MetricCard
    label="Bed Occupancy"
    value={`${occupancy}%`}
    change={`${counts.available} Available, ${counts.cleaning} Cleaning`}
    isPositive={counts.available > 0}
    icon={<BedDouble className="w-4 h-4" />}
  />;
};

export const DashboardSafetyNotice: React.FC = () => <div className="p-4 bg-slate-900 text-slate-300 rounded-lg flex items-center justify-between">
  <div className="flex items-center gap-3">
    <ShieldCheck className="w-5 h-5 text-primary-400 shrink-0" />
    <div className="text-xs">
      <span className="font-semibold text-white">Clinical Safety Architecture:</span>{' '}
      AI summaries remain in draft status until a physician explicitly signs off. Staff manually start bed release after approval, and each turnover step remains an explicit internal action.
    </div>
  </div>
</div>;

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isReceptionist = user?.role === 'receptionist';
  const isSuperintendent =
    user?.role === 'medical_superintendent' ||
    user?.role === 'ward_admin' ||
    user?.role === 'receiving_admin';

  const [beds, setBeds] = useState<BedSummary[]>([]);
  const [bedMetricState, setBedMetricState] = useState<BedMetricState>('loading');
  const loadEpochRef = useRef(0);

  useEffect(() => {
    const epoch = loadEpochRef.current + 1;
    loadEpochRef.current = epoch;
    setBeds([]);
    setBedMetricState('loading');
    listAllBeds()
      .then((loadedBeds) => {
        if (loadEpochRef.current !== epoch) return;
        setBeds(loadedBeds);
        setBedMetricState('ready');
      })
      .catch(() => {
        if (loadEpochRef.current === epoch) setBedMetricState('error');
      });
    return () => {
      if (loadEpochRef.current === epoch) loadEpochRef.current += 1;
    };
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          isReceptionist
            ? 'Inpatient Reception & Registration Desk'
            : isSuperintendent
            ? 'Hospital Operations & Orchestration Command'
            : 'Clinical Operations & Discharge Orchestration'
        }
        description={
          isReceptionist
            ? 'Reception command center for new patient registration, itemized invoices, and counter payments.'
            : isSuperintendent
            ? 'Superintendent command center for bed turnovers, fleet coordination, and hospital capacity.'
            : 'Physician portal for clinical decisions, discharge reviews, and specialized transfer requests.'
        }
        action={
          <div className="flex items-center gap-3">
            {isReceptionist ? (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<Users className="w-4 h-4" />}
                  onClick={() => navigate('/billing/reception')}
                >
                  Billing & Invoices
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<Users className="w-4 h-4" />}
                  onClick={() => navigate('/patients')}
                >
                  Patient Directory
                </Button>
              </>
            ) : isSuperintendent ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<BedDouble className="w-4 h-4" />}
                  onClick={() => navigate('/beds')}
                >
                  Manage Beds
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<Users className="w-4 h-4" />}
                  onClick={() => navigate('/patients')}
                >
                  Patient Directory
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<ArrowRightLeft className="w-4 h-4" />}
                  onClick={() => navigate('/transfers')}
                >
                  Transfer Cases
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<Users className="w-4 h-4" />}
                  onClick={() => navigate('/patients')}
                >
                  My Inpatients
                </Button>
              </>
            )}
          </div>
        }
      />

      {/* KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Admitted Inpatients"
          value="42"
          change="8 Wards Active"
          isPositive={true}
          icon={<Users className="w-4 h-4" />}
        />
        <MetricCard
          label="Discharge Reviews Pending"
          value="4"
          change="Physician sign-off required"
          isPositive={false}
          icon={<FileCheck2 className="w-4 h-4" />}
        />
        <MetricCard
          label="Active Transfers"
          value="2"
          change="1 In-Transit, 1 Matching"
          isPositive={true}
          icon={<ArrowRightLeft className="w-4 h-4" />}
        />
        <DashboardBedMetric beds={beds} state={bedMetricState} />
      </div>

      {/* Clinical Review & Action Queues */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Physician Sign-Off Queue */}
        <Card
          title="Discharge Summaries Awaiting Physician Sign-Off"
          subtitle="AI-generated summaries ready for clinical verification and explicit approval."
          action={
            <Button
              variant="ghost"
              size="sm"
              rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
              onClick={() => navigate('/patients')}
            >
              View All
            </Button>
          }
        >
          <div className="divide-y divide-slate-100">
            <div className="py-3.5 flex items-center justify-between first:pt-0 last:pb-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-slate-900">
                    Eleanor Vance
                  </span>
                  <span className="text-xs text-slate-400">#SYNTH-PAT-001</span>
                  <StatusBadge status="generated" />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Cardiology Ward 3B (Bed B-304) • Dr. Aris Thorne
                </p>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/patients/1/discharge')}
              >
                Review & Sign
              </Button>
            </div>

            <div className="py-3.5 flex items-center justify-between first:pt-0 last:pb-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-slate-900">
                    Marcus Sterling
                  </span>
                  <span className="text-xs text-slate-400">#SYNTH-PAT-002</span>
                  <StatusBadge status="under_review" />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Neurology ICU (Bed NICU-04) • Neurovascular Transfer
                </p>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/patients/2/discharge')}
              >
                Review & Sign
              </Button>
            </div>
          </div>
        </Card>

        {/* Inter-Hospital Transfer Queue */}
        <Card
          title="Active Inter-Hospital Transfers"
          subtitle="Real-time tracking of specialized facility matching and ambulance transit."
          action={
            <Button
              variant="ghost"
              size="sm"
              rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
              onClick={() => navigate('/transfers')}
            >
              Transfer Board
            </Button>
          }
        >
          <div className="divide-y divide-slate-100">
            <div className="py-3.5 flex items-center justify-between first:pt-0 last:pb-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-slate-900">
                    Marcus Sterling
                  </span>
                  <StatusBadge status="in_transit" />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Destination: Bay Neurovascular & Trauma Institute (ETA: 14 mins)
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/transfers/1')}
              >
                Track Transfer
              </Button>
            </div>

            <div className="py-3.5 flex items-center justify-between first:pt-0 last:pb-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-slate-900">
                    Specialty Search
                  </span>
                  <StatusBadge status="matching" />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Pediatric Intensive Care Unit (PICU) transfer inquiry
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/transfers')}
              >
                Inspect
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Safety Protocol Reminder */}
      <DashboardSafetyNotice />
    </div>
  );
};
