import React from 'react';
import {
  FileText,
  Building2,
  User,
  ShieldAlert,
  Send,
  Eye,
  Calendar,
  Pill,
  Activity,
  X,
} from 'lucide-react';
import { TransferPacket } from '../../types';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';

interface TransferPacketModalProps {
  isOpen: boolean;
  packet: TransferPacket | null;
  isLoadingSend?: boolean;
  onSend?: () => void;
  onClose: () => void;
}

export const TransferPacketModal: React.FC<TransferPacketModalProps> = ({
  isOpen,
  packet,
  isLoadingSend = false,
  onSend,
  onClose,
}) => {
  if (!isOpen || !packet) return null;

  const content = packet.packet_content;
  const isEmergency = content.urgency === 'emergency';

  const formatTimestamp = (iso?: string) => {
    if (!iso) return 'Pending';
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100 bg-slate-50/50 rounded-t-2xl">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary-100/80 text-primary-700 rounded-xl">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-900">Clinical Transfer Packet</h3>
                <Badge
                  variant={
                    packet.status === 'viewed'
                      ? 'green'
                      : packet.status === 'sent'
                      ? 'primary'
                      : 'slate'
                  }
                  size="sm"
                >
                  {packet.status.toUpperCase()}
                </Badge>
              </div>
              <p className="text-xs text-slate-500">
                Verified clinical handoff snapshot prepared for destination facility
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="overflow-y-auto p-6 space-y-6 text-xs text-slate-700">
          {/* Emergency Alert */}
          {isEmergency && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <ShieldAlert className="w-5 h-5 text-red-600 shrink-0" />
                <span className="font-bold text-red-950">
                  Emergency Priority Transfer Packet
                </span>
              </div>
              <span className="text-[10px] font-bold uppercase bg-red-200 text-red-900 px-2 py-0.5 rounded">
                Critical
              </span>
            </div>
          )}

          {/* Facility Routing */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200/70">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400 block">
                Sending Facility & Physician
              </span>
              <span className="font-bold text-slate-900 text-sm block mt-0.5 flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-slate-500" />
                {content.sending_hospital.hospital_name}
              </span>
              <span className="text-slate-600 mt-1 block flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-slate-400" />
                {content.sending_doctor.name} {content.sending_doctor.email ? `(${content.sending_doctor.email})` : ''}
              </span>
            </div>

            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400 block">
                Destination Facility & Specialty
              </span>
              <span className="font-bold text-slate-900 text-sm block mt-0.5 flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-green-600" />
                {content.receiving_hospital.hospital_name}
              </span>
              <span className="text-primary-700 font-semibold mt-1 block">
                Required Specialty: {content.required_specialty}
              </span>
            </div>
          </div>

          {/* Patient Demographics */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Patient Identification
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 bg-white border border-slate-200 rounded-xl">
              <div>
                <span className="text-slate-400 block text-[10px]">Name</span>
                <span className="font-bold text-slate-900">{content.patient_summary.patient_name}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Code / Gender</span>
                <span className="font-semibold text-slate-800">
                  {content.patient_summary.patient_code} • {content.patient_summary.gender || 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Blood Group</span>
                <span className="font-semibold text-slate-800">
                  {content.patient_summary.blood_group || 'Not recorded'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Emergency Contact</span>
                <span className="font-semibold text-slate-800">
                  {content.patient_summary.emergency_contact || 'N/A'}
                </span>
              </div>
            </div>
          </div>

          {/* Clinical Justification & Course */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Clinical Assessment & History
            </h4>
            <div className="p-4 bg-primary-50/50 border border-primary-100 rounded-xl space-y-2">
              <div>
                <span className="text-slate-500 block text-[11px] font-semibold">Primary Diagnosis</span>
                <p className="font-bold text-slate-900 text-sm">{content.primary_diagnosis}</p>
              </div>
              <div className="pt-2 border-t border-primary-200/50">
                <span className="text-slate-500 block text-[11px] font-semibold">Transfer Justification</span>
                <p className="text-slate-800 mt-0.5">{content.transfer_reason}</p>
              </div>
              <div className="pt-2 border-t border-primary-200/50">
                <span className="text-slate-500 block text-[11px] font-semibold">Treatment Course</span>
                <p className="text-slate-700 whitespace-pre-wrap mt-0.5">{content.treatment_course}</p>
              </div>
              {content.clinical_notes && (
                <div className="pt-2 border-t border-primary-200/50">
                  <span className="text-slate-500 block text-[11px] font-semibold">Physician Notes</span>
                  <p className="text-slate-700 italic mt-0.5">{content.clinical_notes}</p>
                </div>
              )}
            </div>
          </div>

          {/* Medications Table */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
              <Pill className="w-3.5 h-3.5 text-slate-400" /> Current Active Medications
            </h4>
            {content.current_medications.length === 0 ? (
              <p className="text-slate-400 italic p-3 bg-slate-50 rounded-lg border border-slate-100">
                No active medications recorded.
              </p>
            ) : (
              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left">
                  <thead className="bg-slate-50 text-[10px] uppercase font-semibold text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="px-3 py-2">Medication</th>
                      <th className="px-3 py-2">Dosage</th>
                      <th className="px-3 py-2">Frequency</th>
                      <th className="px-3 py-2">Route</th>
                      <th className="px-3 py-2">Start Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {content.current_medications.map((med, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2 font-semibold text-slate-900">{med.medication_name}</td>
                        <td className="px-3 py-2">{med.dosage}</td>
                        <td className="px-3 py-2">{med.frequency}</td>
                        <td className="px-3 py-2">{med.route}</td>
                        <td className="px-3 py-2 text-slate-500">{med.start_date || 'Ongoing'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent Vitals Table */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-slate-400" /> Recent Vitals (Last Observations)
            </h4>
            {content.recent_vitals.length === 0 ? (
              <p className="text-slate-400 italic p-3 bg-slate-50 rounded-lg border border-slate-100">
                No vitals observations recorded.
              </p>
            ) : (
              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left">
                  <thead className="bg-slate-50 text-[10px] uppercase font-semibold text-slate-500 border-b border-slate-200">
                    <tr>
                      <th className="px-3 py-2">Temperature</th>
                      <th className="px-3 py-2">Heart Rate</th>
                      <th className="px-3 py-2">Blood Pressure</th>
                      <th className="px-3 py-2">SpO₂</th>
                      <th className="px-3 py-2">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {content.recent_vitals.map((v, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2">{v.temperature.toFixed(1)} °C</td>
                        <td className="px-3 py-2 font-semibold text-slate-900">{v.heart_rate} bpm</td>
                        <td className="px-3 py-2">{v.blood_pressure}</td>
                        <td className="px-3 py-2 font-semibold text-green-700">{v.oxygen_saturation}%</td>
                        <td className="px-3 py-2 text-slate-500">{new Date(v.recorded_at).toLocaleTimeString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Packet Audit Metadata */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 flex flex-wrap gap-4 text-[11px] text-slate-500">
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              <span>Prepared: {formatTimestamp(packet.prepared_at)}</span>
            </div>
            {packet.sent_at && (
              <div className="flex items-center gap-1.5">
                <Send className="w-3.5 h-3.5 text-primary-500" />
                <span>Sent: {formatTimestamp(packet.sent_at)}</span>
              </div>
            )}
            {packet.viewed_at && (
              <div className="flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-green-500" />
                <span>Viewed: {formatTimestamp(packet.viewed_at)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50 rounded-b-2xl">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>

          {onSend && packet.status === 'prepared' && (
            <Button
              variant="primary"
              size="sm"
              isLoading={isLoadingSend}
              leftIcon={<Send className="w-3.5 h-3.5" />}
              onClick={onSend}
            >
              Send Packet to Receiving Hospital
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
