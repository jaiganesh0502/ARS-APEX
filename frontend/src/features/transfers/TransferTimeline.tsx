import React from 'react';
import { CheckCircle2, Clock, Ambulance, Check, Building2, Send, Eye, XCircle } from 'lucide-react';
import { TransferPacketStatus, TransferStatus } from '../../types';

interface TransferTimelineProps {
  status: TransferStatus;
  requestedAt: string;
  selectedHospitalAt?: string;
  selectedHospitalName?: string;
  packetStatus?: TransferPacketStatus;
  acceptedAt?: string;
  acceptanceNotes?: string;
  rejectedAt?: string;
  rejectionReason?: string;
  completedAt?: string;
}

export const TransferTimeline: React.FC<TransferTimelineProps> = ({
  status,
  requestedAt,
  selectedHospitalAt,
  selectedHospitalName,
  packetStatus,
  acceptedAt,
  acceptanceNotes,
  rejectedAt,
  rejectionReason,
  completedAt,
}) => {
  const isMatching = status === 'matching';
  const isAwaitingOrBeyond = status !== 'matching' && status !== 'cancelled';
  const isRejected = status === 'rejected';
  const isAcceptedOrBeyond = ['accepted', 'ambulance_requested', 'in_transit', 'completed'].includes(status);
  const isCompleted = status === 'completed';

  const formatTime = (iso?: string) => {
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="space-y-4 text-xs">
      <ol className="relative border-l border-slate-200 ml-3 space-y-6">
        {/* Step 1: Matching Started */}
        <li className="ml-5">
          <div className="absolute -left-2 mt-0.5 w-4 h-4 bg-green-500 rounded-full border-2 border-white flex items-center justify-center text-white">
            <Check className="w-2.5 h-2.5" />
          </div>
          <div>
            <span className="font-bold text-slate-900 block text-xs">Transfer Case Initiated</span>
            <span className="text-slate-500 block text-[11px]">
              Confirmed by Attending Physician • {formatTime(requestedAt)}
            </span>
          </div>
        </li>

        {/* Step 2: Hospital Selected */}
        <li className="ml-5">
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isAwaitingOrBeyond ? 'bg-green-500' : 'bg-slate-300'
            }`}
          >
            {isAwaitingOrBeyond ? <Check className="w-2.5 h-2.5" /> : <Clock className="w-2.5 h-2.5" />}
          </div>
          <div>
            <span
              className={`font-bold block text-xs ${
                isAwaitingOrBeyond ? 'text-slate-900' : 'text-slate-400'
              }`}
            >
              Receiving Facility Selected
            </span>
            {selectedHospitalName ? (
              <div className="mt-1 flex items-center gap-1.5 text-primary-700 font-medium bg-primary-50 px-2 py-1 rounded border border-primary-100 w-fit">
                <Building2 className="w-3.5 h-3.5" />
                <span>{selectedHospitalName}</span>
                <span className="text-slate-500 text-[10px]">
                  ({formatTime(selectedHospitalAt) || 'Awaiting response'})
                </span>
              </div>
            ) : (
              <span className="text-slate-400 block text-[11px]">
                {isMatching ? 'Matching facility in progress...' : 'Pending facility selection'}
              </span>
            )}
          </div>
        </li>

        {/* Step 3: Transfer Packet Status */}
        {selectedHospitalName && (
          <li className="ml-5">
            <div
              className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
                packetStatus === 'viewed'
                  ? 'bg-green-500'
                  : packetStatus === 'sent'
                  ? 'bg-primary-600'
                  : 'bg-slate-300'
              }`}
            >
              {packetStatus === 'viewed' ? (
                <Eye className="w-2.5 h-2.5" />
              ) : packetStatus === 'sent' ? (
                <Send className="w-2.5 h-2.5" />
              ) : (
                <Clock className="w-2.5 h-2.5" />
              )}
            </div>
            <div>
              <span
                className={`font-bold block text-xs ${
                  packetStatus ? 'text-slate-900' : 'text-slate-400'
                }`}
              >
                Clinical Transfer Packet
              </span>
              <span className="text-slate-500 block text-[11px]">
                {packetStatus === 'viewed'
                  ? 'Viewed & Evaluated by Destination Clinical Staff'
                  : packetStatus === 'sent'
                  ? 'Delivered to Destination Review Queue'
                  : 'Packet Prepared & Ready for Delivery'}
              </span>
            </div>
          </li>
        )}

        {/* Step 4: Decision (Accept or Reject) */}
        <li className="ml-5">
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isAcceptedOrBeyond
                ? 'bg-green-500'
                : isRejected
                ? 'bg-red-600'
                : 'bg-slate-300'
            }`}
          >
            {isAcceptedOrBeyond ? (
              <Check className="w-2.5 h-2.5" />
            ) : isRejected ? (
              <XCircle className="w-2.5 h-2.5" />
            ) : (
              <Clock className="w-2.5 h-2.5" />
            )}
          </div>
          <div>
            <span
              className={`font-bold block text-xs ${
                isAcceptedOrBeyond
                  ? 'text-green-950'
                  : isRejected
                  ? 'text-red-950'
                  : 'text-slate-400'
              }`}
            >
              {isAcceptedOrBeyond
                ? 'Receiving Facility Confirmed (Bed Reserved)'
                : isRejected
                ? 'Transfer Request Rejected'
                : 'Receiving Facility Decision'}
            </span>
            <span className="text-slate-500 block text-[11px]">
              {acceptedAt
                ? `Accepted by Receiving Doctor • ${formatTime(acceptedAt)}`
                : rejectedAt
                ? `Rejected • ${formatTime(rejectedAt)}: ${rejectionReason || 'No reason provided'}`
                : 'Pending acceptance & bed reservation'}
            </span>
            {acceptanceNotes && (
              <p className="text-[11px] text-green-800 bg-green-50 p-1.5 rounded border border-green-200 mt-1">
                Note: {acceptanceNotes}
              </p>
            )}
          </div>
        </li>

        {/* Step 5: Transit */}
        <li className={`ml-5 ${isAcceptedOrBeyond ? 'opacity-100' : 'opacity-40'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              status === 'in_transit'
                ? 'bg-purple-600 animate-pulse'
                : status === 'ambulance_requested'
                ? 'bg-primary-600'
                : isCompleted
                ? 'bg-green-500'
                : 'bg-slate-300'
            }`}
          >
            <Ambulance className="w-2.5 h-2.5" />
          </div>
          <div>
            <span className="font-bold text-slate-800 block text-xs">Ambulance Transport</span>
            <span className="text-slate-500 block text-[11px]">
              {status === 'in_transit'
                ? 'Patient in transit to receiving hospital • Bed turnover started'
                : status === 'ambulance_requested'
                ? 'Ambulance dispatched • Vehicle en route to pickup'
                : isCompleted
                ? 'Transit completed'
                : isAcceptedOrBeyond
                ? 'Next step: Ambulance Dispatch'
                : 'Ambulance dispatch on receiving approval'}
            </span>
          </div>
        </li>

        {/* Step 6: Completed */}
        <li className={`ml-5 ${isCompleted ? 'opacity-100' : 'opacity-30'}`}>
          <div
            className={`absolute -left-2 mt-0.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center text-white ${
              isCompleted ? 'bg-green-500' : 'bg-slate-300'
            }`}
          >
            <CheckCircle2 className="w-2.5 h-2.5" />
          </div>
          <div>
            <span className="font-bold text-slate-800 block text-xs">Clinical Handover Complete</span>
            <span className="text-slate-500 block text-[11px]">
              {completedAt ? `Transferred • ${formatTime(completedAt)}` : 'Destination admission'}
            </span>
          </div>
        </li>
      </ol>
    </div>
  );
};
