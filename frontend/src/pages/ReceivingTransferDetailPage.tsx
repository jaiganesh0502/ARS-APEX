import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  FileText,
  AlertTriangle,
} from 'lucide-react';

import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { Spinner } from '../components/common/Spinner';
import { TransferAcceptModal } from '../features/transfers/TransferAcceptModal';
import { TransferRejectModal } from '../features/transfers/TransferRejectModal';
import { TransferPacketModal } from '../features/transfers/TransferPacketModal';
import { TransferTimeline } from '../features/transfers/TransferTimeline';
import { transferApi } from '../api/transfers';
import { TransferDetail, TransferPacket } from '../types';

export const ReceivingTransferDetailPage: React.FC = () => {
  const { transferId } = useParams<{ transferId: string }>();
  const navigate = useNavigate();

  const [transfer, setTransfer] = useState<TransferDetail | null>(null);
  const [packet, setPacket] = useState<TransferPacket | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [isAcceptModalOpen, setIsAcceptModalOpen] = useState(false);
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [isPacketModalOpen, setIsPacketModalOpen] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);

  const fetchTransferData = async () => {
    if (!transferId) return;
    setIsLoading(true);
    setError(null);
    try {
      const id = parseInt(transferId, 10);
      const data = await transferApi.getIncomingTransferDetail(id);
      setTransfer(data);

      try {
        const packetData = await transferApi.getTransferPacket(id, true);
        setPacket(packetData);
      } catch (packetErr) {
        console.warn('Packet fetch warning', packetErr);
      }
    } catch (err) {
      console.error('Failed to load incoming transfer', err);
      setError('Unable to load transfer details or receiving context.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTransferData();
  }, [transferId]);

  const handleAcceptConfirm = async (notes?: string) => {
    if (!transfer) return;
    setIsActionLoading(true);
    try {
      await transferApi.acceptTransfer(transfer.id, notes);
      setIsAcceptModalOpen(false);
      await fetchTransferData();
    } catch (err: unknown) {
      console.error('Accept transfer error', err);
      alert('Failed to accept transfer. Bed capacity may no longer be available.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRejectConfirm = async (reason: string) => {
    if (!transfer) return;
    setIsActionLoading(true);
    try {
      await transferApi.rejectTransfer(transfer.id, reason);
      setIsRejectModalOpen(false);
      await fetchTransferData();
    } catch (err: unknown) {
      console.error('Reject transfer error', err);
      alert('Failed to reject transfer. Please try again.');
    } finally {
      setIsActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Spinner size="lg" />
        <span className="text-sm font-medium text-slate-600 mt-3">
          Loading clinical transfer packet and capacity...
        </span>
      </div>
    );
  }

  if (error || !transfer) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="w-4 h-4" />}
          onClick={() => navigate('/receiving/transfers')}
        >
          Back to Incoming Transfers
        </Button>
        <Card title="Transfer Unavailable">
          <p className="text-sm text-rose-600">{error || 'Transfer request not found.'}</p>
        </Card>
      </div>
    );
  }

  const isAwaitingAcceptance =
    transfer.status === 'awaiting_acceptance' || transfer.status === 'hospital_selected';
  const isAccepted = transfer.status === 'accepted';
  const isRejected = transfer.status === 'rejected';

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Navigation Header */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="w-4 h-4" />}
          onClick={() => navigate('/receiving/transfers')}
        >
          Back to Incoming Transfers
        </Button>

        {packet && (
          <Button
            variant="outline"
            size="sm"
            leftIcon={<FileText className="w-4 h-4" />}
            onClick={() => setIsPacketModalOpen(true)}
          >
            View Full Clinical Packet
          </Button>
        )}
      </div>

      {/* Page Title with Action Status */}
      <PageHeader
        title={`Transfer Evaluation: #TRF-00${transfer.id}`}
        description="Review clinical justification, assess local bed capacity, and record receiving physician decision."
        action={<StatusBadge status={transfer.status} />}
      />

      {/* Emergency Alert Banner */}
      {transfer.emergency && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-rose-600 text-white rounded-lg">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-rose-950 text-sm block">
                Emergency Priority Transfer Request
              </span>
              <span className="text-xs text-rose-800">
                Patient requires expedited admission for {transfer.required_specialty}. Please review and respond promptly.
              </span>
            </div>
          </div>
          <span className="px-3 py-1 bg-rose-200/80 text-rose-950 font-bold text-xs rounded-full uppercase">
            Emergency
          </span>
        </div>
      )}

      {/* Decision Status Banners */}
      {isAccepted && (
        <div className="p-5 bg-emerald-50 border-2 border-emerald-300 rounded-2xl shadow-sm space-y-2">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-600 text-white rounded-lg">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-extrabold text-emerald-950">
                Transfer Accepted & Bed Capacity Reserved
              </h4>
              <span className="text-xs text-emerald-800">
                1 bed slot has been reserved in <strong>{transfer.required_specialty}</strong>. Awaiting ambulance dispatch coordination.
              </span>
            </div>
          </div>
          {transfer.acceptance_notes && (
            <p className="text-xs text-emerald-900 bg-white/70 p-2.5 rounded-lg border border-emerald-200 mt-2">
              <strong>Physician Notes:</strong> {transfer.acceptance_notes}
            </p>
          )}
        </div>
      )}

      {isRejected && (
        <div className="p-5 bg-rose-50 border-2 border-rose-300 rounded-2xl shadow-sm space-y-2">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-rose-600 text-white rounded-lg">
              <XCircle className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-extrabold text-rose-950">
                Transfer Request Rejected
              </h4>
              <span className="text-xs text-rose-800">
                The sending facility has been notified. No bed capacity was decremented.
              </span>
            </div>
          </div>
          {transfer.rejection_reason && (
            <p className="text-xs text-rose-900 bg-white/70 p-2.5 rounded-lg border border-rose-200 mt-2">
              <strong>Rejection Justification:</strong> {transfer.rejection_reason}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Clinical Transfer Packet Overview */}
        <div className="space-y-6 lg:col-span-2">
          {/* Patient Details */}
          <Card title="Patient Profile & Demographics">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Patient Name</span>
                <span className="font-bold text-slate-900 text-sm block mt-0.5">
                  {transfer.patient_name}
                </span>
                <span className="text-slate-500 font-mono text-[11px]">{transfer.patient_code}</span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Required Specialty</span>
                <span className="font-bold text-blue-700 text-sm block mt-0.5">
                  {transfer.required_specialty}
                </span>
                <span className="text-slate-500 text-[11px]">
                  Priority: {transfer.emergency ? 'Emergency' : 'Standard'}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Origin Facility</span>
                <span className="font-semibold text-slate-900 block mt-0.5">
                  {transfer.sending_hospital_name}
                </span>
                <span className="text-slate-500 text-[11px]">
                  Doctor: {transfer.requested_by_name || 'Attending Physician'}
                </span>
              </div>
            </div>

            {/* Clinical Justification Box */}
            <div className="mt-4 p-4 bg-blue-50/60 rounded-xl border border-blue-100 space-y-2 text-xs">
              <div>
                <span className="text-slate-500 font-semibold block text-[11px]">Primary Diagnosis:</span>
                <p className="font-bold text-slate-900 text-sm">{transfer.primary_diagnosis}</p>
              </div>
              <div className="pt-2 border-t border-blue-200/50">
                <span className="text-slate-500 font-semibold block text-[11px]">Transfer Reason:</span>
                <p className="text-blue-950 mt-0.5">
                  {transfer.clinical_reason || 'Specialized tertiary care required.'}
                </p>
              </div>
              {transfer.clinical_notes && (
                <div className="pt-2 border-t border-blue-200/50">
                  <span className="text-slate-500 font-semibold block text-[11px]">Clinical Notes:</span>
                  <p className="text-blue-900 italic mt-0.5">{transfer.clinical_notes}</p>
                </div>
              )}
            </div>
          </Card>

          {/* Active Medications */}
          {packet?.packet_content.current_medications && (
            <Card title="Current Medications" subtitle="Administered at origin facility">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[10px] uppercase font-semibold text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="px-3 py-2">Medication</th>
                      <th className="px-3 py-2">Dosage</th>
                      <th className="px-3 py-2">Frequency</th>
                      <th className="px-3 py-2">Route</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {packet.packet_content.current_medications.map((med, idx) => (
                      <tr key={idx}>
                        <td className="px-3 py-2 font-semibold text-slate-900">{med.medication_name}</td>
                        <td className="px-3 py-2">{med.dosage}</td>
                        <td className="px-3 py-2">{med.frequency}</td>
                        <td className="px-3 py-2">{med.route}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Recent Vitals */}
          {packet?.packet_content.recent_vitals && (
            <Card title="Recent Observations" subtitle="Latest vital telemetry recordings">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[10px] uppercase font-semibold text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="px-3 py-2">Temperature</th>
                      <th className="px-3 py-2">Heart Rate</th>
                      <th className="px-3 py-2">Blood Pressure</th>
                      <th className="px-3 py-2">SpO₂</th>
                      <th className="px-3 py-2">Recorded At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {packet.packet_content.recent_vitals.map((v, idx) => (
                      <tr key={idx}>
                        <td className="px-3 py-2">{v.temperature.toFixed(1)} °C</td>
                        <td className="px-3 py-2 font-bold text-slate-900">{v.heart_rate} bpm</td>
                        <td className="px-3 py-2">{v.blood_pressure}</td>
                        <td className="px-3 py-2 font-bold text-emerald-700">{v.oxygen_saturation}%</td>
                        <td className="px-3 py-2 text-slate-500">{new Date(v.recorded_at).toLocaleTimeString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Capacity Status & Action Controls */}
        <div className="space-y-6">
          {/* Action Decision Card */}
          {isAwaitingAcceptance && (
            <Card title="Receiving Decision" subtitle="Attending physician evaluation">
              <div className="space-y-4 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-bold uppercase text-slate-500 block">
                      Local Specialty Capacity
                    </span>
                    <span className="font-bold text-slate-900 text-sm">
                      {transfer.required_specialty}
                    </span>
                  </div>
                  <div className="text-right">
                    <span
                      className={`text-lg font-black block ${
                        (transfer.receiving_hospital_available_beds ?? 0) > 0
                          ? 'text-emerald-700'
                          : 'text-rose-600'
                      }`}
                    >
                      {transfer.receiving_hospital_available_beds ?? 'N/A'} beds free
                    </span>
                  </div>
                </div>

                {(transfer.receiving_hospital_available_beds ?? 0) <= 0 && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-[11px] flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <span>No bed capacity currently available. Acceptance cannot proceed.</span>
                  </div>
                )}

                <div className="space-y-2 pt-2">
                  <Button
                    variant="primary"
                    size="md"
                    className="w-full"
                    disabled={(transfer.receiving_hospital_available_beds ?? 0) <= 0}
                    leftIcon={<CheckCircle2 className="w-4 h-4" />}
                    onClick={() => setIsAcceptModalOpen(true)}
                  >
                    Accept Transfer & Hold Bed
                  </Button>

                  <Button
                    variant="outline"
                    size="md"
                    className="w-full border-rose-300 text-rose-700 hover:bg-rose-50"
                    leftIcon={<XCircle className="w-4 h-4" />}
                    onClick={() => setIsRejectModalOpen(true)}
                  >
                    Reject Transfer
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Progression Timeline */}
          <Card title="Transfer Milestones">
            <TransferTimeline
              status={transfer.status}
              requestedAt={transfer.requested_at}
              selectedHospitalAt={transfer.selected_hospital_at}
              selectedHospitalName={transfer.receiving_hospital_name}
              packetStatus={transfer.packet_status}
              acceptedAt={transfer.accepted_at}
              acceptanceNotes={transfer.acceptance_notes}
              rejectedAt={transfer.rejected_at}
              rejectionReason={transfer.rejection_reason}
              completedAt={transfer.completed_at}
            />
          </Card>
        </div>
      </div>

      {/* Acceptance Modal */}
      <TransferAcceptModal
        isOpen={isAcceptModalOpen}
        patientName={transfer.patient_name}
        specialty={transfer.required_specialty}
        hospitalName={transfer.receiving_hospital_name}
        availableBeds={transfer.receiving_hospital_available_beds}
        isLoading={isActionLoading}
        onClose={() => setIsAcceptModalOpen(false)}
        onConfirm={handleAcceptConfirm}
      />

      {/* Rejection Modal */}
      <TransferRejectModal
        isOpen={isRejectModalOpen}
        patientName={transfer.patient_name}
        specialty={transfer.required_specialty}
        sendingHospitalName={transfer.sending_hospital_name}
        isLoading={isActionLoading}
        onClose={() => setIsRejectModalOpen(false)}
        onConfirm={handleRejectConfirm}
      />

      {/* Packet Modal */}
      <TransferPacketModal
        isOpen={isPacketModalOpen}
        packet={packet}
        onClose={() => setIsPacketModalOpen(false)}
      />
    </div>
  );
};
