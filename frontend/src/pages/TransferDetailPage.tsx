import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  ShieldAlert,
  BedDouble,
  Navigation,
  Phone,
  ExternalLink,
  FileText,
  Send,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Ambulance,
  Clock,
} from 'lucide-react';

import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Spinner } from '../components/common/Spinner';
import { TransferTimeline } from '../features/transfers/TransferTimeline';
import { TransferPacketModal } from '../features/transfers/TransferPacketModal';
import { transferApi } from '../api/transfers';
import { billingApi } from '../api/billing';
import { TransferDetail, TransferPacket, AmbulanceDispatch, BillingClearance } from '../types';

export const TransferDetailPage: React.FC = () => {
  const { transferId } = useParams<{ transferId: string }>();
  const navigate = useNavigate();

  const [transfer, setTransfer] = useState<TransferDetail | null>(null);
  const [packet, setPacket] = useState<TransferPacket | null>(null);
  const [ambulance, setAmbulance] = useState<AmbulanceDispatch | null>(null);
  const [billing, setBilling] = useState<BillingClearance | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Action states
  const [isPacketModalOpen, setIsPacketModalOpen] = useState(false);
  const [isSendingPacket, setIsSendingPacket] = useState(false);
  const [isRematching, setIsRematching] = useState(false);
  const [isDispatchingAmbulance, setIsDispatchingAmbulance] = useState(false);

  const fetchTransferData = async () => {
    if (!transferId) return;
    setIsLoading(true);
    setError(null);
    try {
      const id = parseInt(transferId, 10);
      const data = await transferApi.getTransfer(id);
      setTransfer(data);

      // Load packet if receiving hospital is assigned
      if (data.receiving_hospital_id) {
        try {
          const packetData = await transferApi.getTransferPacket(id, false);
          setPacket(packetData);
        } catch (packetErr) {
          console.warn('Could not load packet', packetErr);
        }
      }

      // Load ambulance dispatch if accepted or beyond
      if (['accepted', 'ambulance_requested', 'in_transit', 'completed'].includes(data.status)) {
        try {
          const ambData = await transferApi.getTransferAmbulance(id);
          setAmbulance(ambData);
        } catch (ambErr) {
          console.warn('Could not load ambulance dispatch', ambErr);
        }
      }

      // Load billing clearance
      if (data.admission_id) {
        try {
          const billingData = await billingApi.getAdmissionBillingClearance(data.admission_id);
          setBilling(billingData);
        } catch {
          setBilling(null);
        }
      }
    } catch (err) {
      console.error('Failed to load transfer detail', err);
      setError('Transfer case not found or failed to load.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTransferData();
  }, [transferId]);

  const handleDispatchAmbulance = async () => {
    if (!transfer) return;
    setIsDispatchingAmbulance(true);
    try {
      const amb = await transferApi.dispatchAmbulance(transfer.id);
      setAmbulance(amb);
      await fetchTransferData();
    } catch (err) {
      console.error('Failed to dispatch ambulance', err);
      alert('Unable to dispatch ambulance. Please verify transfer acceptance.');
    } finally {
      setIsDispatchingAmbulance(false);
    }
  };

  const handleSendPacket = async () => {
    if (!transfer) return;
    setIsSendingPacket(true);
    try {
      const updatedPacket = await transferApi.sendTransferPacket(transfer.id);
      setPacket(updatedPacket);
      await fetchTransferData();
    } catch (err) {
      console.error('Failed to send transfer packet', err);
      alert('Unable to send packet. Please try again.');
    } finally {
      setIsSendingPacket(false);
    }
  };

  const handleRematch = async () => {
    if (!transfer) return;
    setIsRematching(true);
    try {
      await transferApi.rematchTransfer(transfer.id);
      navigate(`/transfers/new?patientId=${transfer.patient_id}&admissionId=${transfer.admission_id}`);
    } catch (err) {
      console.error('Failed to re-match transfer', err);
      alert('Unable to re-open hospital matching. Please try again.');
    } finally {
      setIsRematching(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Spinner size="lg" />
        <span className="text-sm font-medium text-slate-600 mt-3">Loading transfer details...</span>
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
          onClick={() => navigate('/transfers')}
        >
          Back to Transfers
        </Button>
        <Card title="Transfer Error">
          <p className="text-sm text-red-600">{error || 'Transfer case not found.'}</p>
        </Card>
      </div>
    );
  }

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
          onClick={() => navigate('/transfers')}
        >
          Back to Transfer Board
        </Button>

        <div className="flex items-center gap-2">
          {packet && (
            <Button
              variant="outline"
              size="sm"
              leftIcon={<FileText className="w-3.5 h-3.5" />}
              onClick={() => setIsPacketModalOpen(true)}
            >
              View Transfer Packet
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
            onClick={() => navigate(`/patients/${transfer.patient_id}`)}
          >
            View Patient Chart
          </Button>
        </div>
      </div>

      <PageHeader
        title={`Transfer Tracking: #TRF-00${transfer.id}`}
        description="Comprehensive clinical handoff telemetry, destination facility status, and transfer timeline."
        action={<StatusBadge status={transfer.status} />}
      />

      {/* Emergency Alert Banner */}
      {transfer.emergency && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-600 text-white rounded-lg">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-red-950 text-sm block">
                Emergency Inter-Hospital Transfer
              </span>
              <span className="text-xs text-red-800">
                Rapid transit protocol prioritized. Distance weight was elevated to 65% during facility ranking.
              </span>
            </div>
          </div>
          <span className="px-3 py-1 bg-red-200/80 text-red-950 font-bold text-xs rounded-full uppercase">
            Emergency
          </span>
        </div>
      )}

      {/* Acceptance Success Banner */}
      {isAccepted && (
        <div className="p-5 bg-green-50 border-2 border-green-300 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-green-600 text-white rounded-xl">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs font-bold text-green-800 uppercase tracking-wider block">
                  Receiving Hospital Confirmed
                </span>
                <h4 className="text-lg font-extrabold text-green-950">
                  {transfer.receiving_hospital_name} — Bed Capacity Reserved
                </h4>
              </div>
            </div>
            <Badge variant="green" size="md">
              CAPACITY RESERVED
            </Badge>
          </div>

          <div className="p-3.5 bg-white/80 rounded-xl border border-green-200 text-xs text-green-900 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Ambulance className="w-5 h-5 text-green-700 shrink-0" />
              <div>
                <strong>Next Step: Ambulance Transport Dispatch</strong>
                <p className="text-[11px] text-green-800">
                  Trigger emergency transit coordination and calculate simulated route ETA.
                </p>
              </div>
            </div>
            <Button
              variant="primary"
              size="sm"
              isLoading={isDispatchingAmbulance}
              leftIcon={<Ambulance className="w-4 h-4" />}
              onClick={handleDispatchAmbulance}
            >
              Dispatch Ambulance
            </Button>
          </div>
        </div>
      )}

      {/* Ambulance Dispatch Active Tracking Banner */}
      {ambulance && transfer.status !== 'accepted' && transfer.status !== 'rejected' && (
        <div className="p-5 bg-primary-50 border-2 border-primary-300 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-primary-600 text-white rounded-xl">
                <Ambulance className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs font-bold text-primary-800 uppercase tracking-wider block">
                  Emergency Transport En Route
                </span>
                <h4 className="text-lg font-extrabold text-primary-950">
                  Dispatch #{ambulance.dispatch_reference} — {ambulance.vehicle_number || 'TN-DEMO-101'}
                </h4>
              </div>
            </div>
            <Button
              variant="primary"
              size="sm"
              rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
              onClick={() => navigate(`/ambulances/${ambulance.id}`)}
            >
              View Ambulance Tracking
            </Button>
          </div>

          <div className="p-3 bg-white/80 rounded-xl border border-primary-200 text-xs text-primary-900 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <span className="text-[10px] text-slate-500 font-semibold block">STATUS</span>
                <StatusBadge status={ambulance.status} />
              </div>
              <div>
                <span className="text-[10px] text-slate-500 font-semibold block">SIMULATED ETA</span>
                <span className="font-bold text-primary-950 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-primary-600" />
                  {ambulance.status === 'completed' ? 'Arrived' : `${ambulance.current_eta_minutes} mins`}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 font-semibold block">ROUTE DISTANCE</span>
                <span className="font-bold text-slate-800">{ambulance.distance_km} km</span>
              </div>
            </div>

            <span className="text-[11px] font-mono text-slate-500">
              Driver: {ambulance.driver_name || 'Rajesh Sharma'}
            </span>
          </div>
        </div>
      )}

      {/* Rejection Alert Banner with Rematch Option */}
      {isRejected && (
        <div className="p-5 bg-red-50 border-2 border-red-300 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-red-600 text-white rounded-xl">
                <XCircle className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs font-bold text-red-800 uppercase tracking-wider block">
                  Transfer Request Rejected
                </span>
                <h4 className="text-base font-extrabold text-red-950">
                  {transfer.receiving_hospital_name} was unable to accept this case
                </h4>
              </div>
            </div>

            <Button
              variant="primary"
              size="sm"
              isLoading={isRematching}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              onClick={handleRematch}
            >
              Find Another Hospital
            </Button>
          </div>

          {transfer.rejection_reason && (
            <p className="text-xs text-red-900 bg-white/70 p-3 rounded-lg border border-red-200">
              <strong>Facility Justification:</strong> {transfer.rejection_reason}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Patient & Clinical Reason */}
        <div className="space-y-6 lg:col-span-2">
          {/* Patient Details Card */}
          <Card title="Patient & Clinical Profile">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Patient Name</span>
                <span className="font-bold text-slate-900 text-sm block mt-0.5">
                  {transfer.patient_name}
                </span>
                <span className="text-slate-500 font-mono text-[11px]">{transfer.patient_code}</span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Primary Diagnosis</span>
                <span className="font-semibold text-slate-900 block mt-0.5">
                  {transfer.primary_diagnosis}
                </span>
                <span className="text-slate-500 text-[11px]">
                  {transfer.ward ? `${transfer.ward} • Bed ${transfer.bed_number}` : 'Inpatient'}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                <span className="text-slate-500 block">Required Specialty</span>
                <span className="font-bold text-primary-700 text-sm block mt-0.5">
                  {transfer.required_specialty}
                </span>
                <span className="text-slate-500 text-[11px]">
                  Priority: {transfer.emergency ? 'Emergency' : 'Standard'}
                </span>
              </div>
            </div>

            {/* Clinical Reason Box */}
            <div className="mt-4 p-3.5 bg-primary-50/50 rounded-xl border border-primary-100 text-xs">
              <span className="font-bold text-primary-950 block mb-1">
                Clinical Reason for Transfer:
              </span>
              <p className="text-primary-900">
                {transfer.clinical_reason || 'Specialized tertiary care required.'}
              </p>
              {transfer.clinical_notes && (
                <p className="text-primary-800/80 mt-1 italic">
                  Notes: {transfer.clinical_notes}
                </p>
              )}
            </div>
          </Card>

          {/* Facility Routing Card */}
          <Card title="Facility Handoff Information">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {/* Origin */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                  Origin (Sending Facility)
                </span>
                <h4 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                  <Building2 className="w-4 h-4 text-slate-500" />
                  {transfer.sending_hospital_name}
                </h4>
                {transfer.sending_hospital_contact && (
                  <span className="text-slate-600 flex items-center gap-1">
                    <Phone className="w-3 h-3 text-slate-400" /> {transfer.sending_hospital_contact}
                  </span>
                )}
                <span className="text-[11px] text-slate-500 block">
                  Attending Doctor: {transfer.requested_by_name || 'Dr. Asha Rao'}
                </span>
              </div>

              {/* Destination */}
              <div
                className={`p-4 rounded-xl border space-y-2 ${
                  transfer.receiving_hospital_name
                    ? 'bg-green-50/40 border-green-200'
                    : 'bg-amber-50/40 border-amber-200'
                }`}
              >
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                  Destination (Receiving Facility)
                </span>
                {transfer.receiving_hospital_name ? (
                  <>
                    <h4 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                      <Building2 className="w-4 h-4 text-green-600" />
                      {transfer.receiving_hospital_name}
                    </h4>
                    {transfer.receiving_hospital_contact && (
                      <span className="text-slate-600 flex items-center gap-1">
                        <Phone className="w-3 h-3 text-slate-400" /> {transfer.receiving_hospital_contact}
                      </span>
                    )}
                    <div className="flex items-center gap-4 text-[11px] text-slate-700 pt-1">
                      {transfer.receiving_hospital_distance_km !== null &&
                        transfer.receiving_hospital_distance_km !== undefined && (
                          <span className="flex items-center gap-1 font-semibold">
                            <Navigation className="w-3 h-3 text-slate-400" />
                            {transfer.receiving_hospital_distance_km} km
                          </span>
                        )}
                      {transfer.receiving_hospital_available_beds !== null &&
                        transfer.receiving_hospital_available_beds !== undefined && (
                          <span className="flex items-center gap-1 text-green-700 font-semibold">
                            <BedDouble className="w-3 h-3 text-green-500" />
                            {transfer.receiving_hospital_available_beds} beds free
                          </span>
                        )}
                    </div>
                  </>
                ) : (
                  <div>
                    <span className="text-amber-800 font-semibold block text-xs">
                      Matching in Progress...
                    </span>
                    <p className="text-[11px] text-amber-700 mt-1">
                      No receiving facility has been selected yet.
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      className="mt-3"
                      onClick={() =>
                        navigate(
                          `/transfers/new?patientId=${transfer.patient_id}&admissionId=${transfer.admission_id}`
                        )
                      }
                    >
                      Find & Select Facility
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </Card>

          {/* Transfer Packet Section */}
          {transfer.receiving_hospital_id && (
            <Card
              title="Clinical Transfer Packet"
              subtitle="Structured handoff payload snapshot for receiving physician"
              action={
                packet?.status === 'prepared' ? (
                  <Button
                    variant="primary"
                    size="sm"
                    isLoading={isSendingPacket}
                    leftIcon={<Send className="w-3.5 h-3.5" />}
                    onClick={handleSendPacket}
                  >
                    Send Packet
                  </Button>
                ) : (
                  <Badge
                    variant={
                      packet?.status === 'viewed'
                        ? 'green'
                        : packet?.status === 'sent'
                        ? 'primary'
                        : 'slate'
                    }
                    size="sm"
                  >
                    {packet ? packet.status.toUpperCase() : 'PREPARING'}
                  </Badge>
                )
              }
            >
              <div className="space-y-3 text-xs text-slate-600">
                <p>
                  A complete clinical snapshot containing patient demographics, treatment history, active medications, and vital signs has been generated for <strong>{transfer.receiving_hospital_name}</strong>.
                </p>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <span className="text-[11px] text-slate-400">
                    Packet Status:{' '}
                    <strong className="text-slate-800">
                      {packet?.status === 'viewed'
                        ? 'Evaluated by Receiving Facility'
                        : packet?.status === 'sent'
                        ? 'Delivered to Receiving Queue'
                        : 'Prepared (Ready to Send)'}
                    </strong>
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    leftIcon={<FileText className="w-3.5 h-3.5" />}
                    onClick={() => setIsPacketModalOpen(true)}
                  >
                    Review Snapshot
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Workflow Progression Timeline */}
        <div className="space-y-6">
          <Card title="Transfer Progression Timeline">
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

          {/* Billing Clearance Status */}
          <Card
            title="Billing Clearance Gate"
            action={
              transfer.emergency || billing?.status === 'deferred' ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-primary-100 text-primary-800">
                  DEFERRED (EMERGENCY)
                </span>
              ) : billing?.status === 'cleared' ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-green-100 text-green-800">
                  CLEARED
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800">
                  PENDING CLEARANCE
                </span>
              )
            }
          >
            <div className="space-y-2 text-xs text-slate-600">
              {transfer.emergency || billing?.status === 'deferred' ? (
                <div className="p-3 bg-primary-50 border border-primary-200 rounded-lg text-primary-900 text-xs">
                  <p className="font-semibold">Emergency Transfer Clearance Bypass</p>
                  <p className="mt-1 text-[11px] text-primary-800">
                    Billing clearance is deferred post-hoc so critical emergency transfer is never delayed.
                  </p>
                </div>
              ) : billing?.status === 'cleared' ? (
                <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-green-900 text-xs">
                  <p className="font-semibold">Clearance Verified</p>
                  <p className="mt-1 text-[11px] text-green-800 font-mono">
                    Ref: {billing.clearance_reference || 'N/A'}
                  </p>
                </div>
              ) : (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-xs">
                  <p className="font-semibold">Standard Transfer Billing Verification</p>
                  <p className="mt-1 text-[11px] text-amber-800">
                    Bed reservation and ambulance dispatch proceed; transfer handoff packet requires billing clearance.
                  </p>
                </div>
              )}
            </div>
          </Card>

          {/* Transfer Case Meta */}
          <Card title="Audit & Records">
            <div className="space-y-2 text-xs text-slate-600">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Transfer Case ID:</span>
                <span className="font-mono font-semibold text-slate-800">#TRF-00{transfer.id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Admission Ref:</span>
                <span className="font-mono font-semibold text-slate-800">#{transfer.admission_id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Requested By:</span>
                <span className="font-semibold text-slate-800">
                  {transfer.requested_by_name || 'Dr. Asha Rao'}
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-400">Initiated At:</span>
                <span className="text-slate-700">
                  {new Date(transfer.requested_at).toLocaleString()}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Packet Modal */}
      <TransferPacketModal
        isOpen={isPacketModalOpen}
        packet={packet}
        isLoadingSend={isSendingPacket}
        onSend={handleSendPacket}
        onClose={() => setIsPacketModalOpen(false)}
      />
    </div>
  );
};
