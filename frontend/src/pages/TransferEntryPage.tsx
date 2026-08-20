import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  ShieldAlert,
  Search,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react';

import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { PageHeader } from '../components/common/PageHeader';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/StatusBadge';
import { HospitalMatchCard } from '../features/transfers/HospitalMatchCard';
import { HospitalSelectionModal } from '../features/transfers/HospitalSelectionModal';
import { getPatientById } from '../api/patients';
import { getClinicalDecision } from '../api/clinicalDecisions';
import { transferApi } from '../api/transfers';
import {
  ClinicalDecision,
  HospitalMatch,
  PatientDetail,
  Transfer,
} from '../types';

export const TransferEntryPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const patientIdParam = searchParams.get('patientId');
  const admissionIdParam = searchParams.get('admissionId');

  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [decision, setDecision] = useState<ClinicalDecision | null>(null);
  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [matches, setMatches] = useState<HospitalMatch[]>([]);

  const [isLoadingInitial, setIsLoadingInitial] = useState(true);
  const [isSearchingMatches, setIsSearchingMatches] = useState(false);
  const [isSubmittingSelection, setIsSubmittingSelection] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modal State
  const [selectedMatchForModal, setSelectedMatchForModal] = useState<HospitalMatch | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      setIsLoadingInitial(true);
      setErrorMessage(null);

      try {
        if (!patientIdParam) {
          setErrorMessage('No patient specified for transfer preparation.');
          setIsLoadingInitial(false);
          return;
        }

        const patientId = parseInt(patientIdParam, 10);
        if (isNaN(patientId)) {
          setErrorMessage('Invalid patient identifier.');
          setIsLoadingInitial(false);
          return;
        }

        const patientData = await getPatientById(patientId);
        setPatient(patientData);

        const admissionId =
          admissionIdParam ? parseInt(admissionIdParam, 10) : patientData.admission?.id;

        if (!admissionId) {
          setErrorMessage('No active admission found for this patient.');
          setIsLoadingInitial(false);
          return;
        }

        // Fetch Clinical Decision
        try {
          const decisionData = await getClinicalDecision(admissionId);
          setDecision(decisionData);

          if (decisionData.decision_type !== 'transfer') {
            setErrorMessage(
              'The clinical decision for this patient is normal discharge, not inter-hospital transfer.'
            );
          } else if (decisionData.status !== 'confirmed') {
            setErrorMessage(
              'A confirmed physician transfer decision is required before initiating hospital matching.'
            );
          } else {
            // Check or initialize transfer case
            const transferCase = await transferApi.createTransferForAdmission(admissionId);
            setTransfer(transferCase);

            // If transfer exists and is matching or selected, auto-load matches
            if (transferCase.status === 'matching' || transferCase.status === 'hospital_selected' || transferCase.status === 'awaiting_acceptance') {
              try {
                const existingMatches = await transferApi.getHospitalMatches(transferCase.id);
                setMatches(existingMatches);
              } catch (matchErr) {
                console.warn('Could not auto-fetch matches', matchErr);
              }
            }
          }
        } catch (decErr) {
          console.error('Failed to load clinical decision', decErr);
          setErrorMessage('Could not find a confirmed clinical transfer decision for this admission.');
        }
      } catch (err: unknown) {
        console.error('Error loading patient data', err);
        setErrorMessage('Failed to load patient or admission details.');
      } finally {
        setIsLoadingInitial(false);
      }
    };

    loadData();
  }, [patientIdParam, admissionIdParam]);

  const handleFindHospitals = async () => {
    if (!patient?.admission?.id) return;
    setIsSearchingMatches(true);
    setErrorMessage(null);

    try {
      let currentTransfer = transfer;
      if (!currentTransfer) {
        currentTransfer = await transferApi.createTransferForAdmission(patient.admission.id);
        setTransfer(currentTransfer);
      }

      const matchResults = await transferApi.getHospitalMatches(currentTransfer.id);
      setMatches(matchResults);
    } catch (err: unknown) {
      console.error('Error finding hospital matches', err);
      setErrorMessage('Unable to retrieve partner hospital matches. Please try again.');
    } finally {
      setIsSearchingMatches(false);
    }
  };

  const handleSelectHospitalClick = (match: HospitalMatch) => {
    setSelectedMatchForModal(match);
    setIsModalOpen(true);
  };

  const handleConfirmSelection = async () => {
    if (!transfer || !selectedMatchForModal) return;
    setIsSubmittingSelection(true);

    try {
      const updatedTransfer = await transferApi.selectReceivingHospital(
        transfer.id,
        selectedMatchForModal.hospital_id
      );
      setTransfer(updatedTransfer);
      setIsModalOpen(false);
    } catch (err: unknown) {
      console.error('Failed to select receiving hospital', err);
      alert('Failed to select hospital. Please try again.');
    } finally {
      setIsSubmittingSelection(false);
    }
  };

  const isEmergency = decision?.transfer_urgency === 'emergency' || transfer?.emergency;
  const isAwaitingAcceptance =
    transfer?.status === 'awaiting_acceptance' ||
    transfer?.status === 'accepted' ||
    transfer?.status === 'hospital_selected';

  const selectedHospitalName =
    matches.find((m) => m.hospital_id === transfer?.receiving_hospital_id)?.hospital_name ||
    (isAwaitingAcceptance && transfer?.receiving_hospital_id ? `Hospital #${transfer.receiving_hospital_id}` : null);

  if (isLoadingInitial) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Spinner size="lg" />
        <span className="text-sm font-medium text-slate-600 mt-4">
          Loading patient transfer details...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Back Button */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<ArrowLeft className="h-4 w-4" />}
          onClick={() => navigate(patient ? `/patients/${patient.id}` : '/transfers')}
        >
          Back to Patient Profile
        </Button>

        {transfer && (
          <Button
            variant="outline"
            size="sm"
            rightIcon={<ExternalLink className="h-3.5 w-3.5" />}
            onClick={() => navigate(`/transfers/${transfer.id}`)}
          >
            View Transfer Board
          </Button>
        )}
      </div>

      {/* Page Header */}
      <PageHeader
        title="Prepare Patient Transfer"
        description="Rank accredited tertiary partner facilities based on specialty, capacity, and distance, then select the receiving facility."
      />

      {/* Error Alert */}
      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 text-sm text-red-800">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block">Transfer Ineligible</span>
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      {/* Emergency Notice Banner */}
      {isEmergency && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-600 text-white rounded-lg">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-red-950 text-sm block">
                Emergency Transfer Priority
              </span>
              <span className="text-xs text-red-800">
                Distance is prioritized more heavily (65% weight) for rapid emergency transfer matching.
              </span>
            </div>
          </div>
          <span className="px-3 py-1 bg-red-200/80 text-red-950 font-bold text-xs rounded-full uppercase tracking-wider">
            Critical Transit
          </span>
        </div>
      )}

      {/* Patient & Clinical Handoff Summary */}
      {patient && (
        <Card title="Patient Transfer Profile" subtitle="Origin clinical status and specialty requirements">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-slate-500 block">Patient</span>
              <span className="font-bold text-slate-900 text-sm block mt-0.5">
                {patient.demographics.first_name} {patient.demographics.last_name}
              </span>
              <span className="text-slate-500 font-mono text-[11px]">{patient.patient_code}</span>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-slate-500 block">Primary Diagnosis</span>
              <span className="font-semibold text-slate-900 block mt-0.5">
                {patient.admission?.primary_diagnosis || 'Under Review'}
              </span>
              <span className="text-slate-500 text-[11px]">
                {patient.bed ? `${patient.bed.ward} • Bed ${patient.bed.bed_number}` : 'Inpatient'}
              </span>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-slate-500 block">Sending Facility</span>
              <span className="font-semibold text-slate-900 block mt-0.5">
                Metro Multispeciality Medical Center
              </span>
              <span className="text-slate-500 text-[11px]">Host Origin</span>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-slate-500 block">Required Specialty</span>
              <span className="font-bold text-primary-700 text-sm block mt-0.5">
                {decision?.required_specialty || 'General Medicine'}
              </span>
              <span className="text-slate-500 text-[11px]">
                Urgency: {isEmergency ? 'Emergency' : 'Standard'}
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* Selected Facility Status Banner (If already selected) */}
      {isAwaitingAcceptance && (
        <div className="p-5 bg-green-50 border-2 border-green-300 rounded-2xl shadow-sm space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-green-600 text-white rounded-xl">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs font-bold text-green-800 uppercase tracking-wider block">
                  Receiving Hospital Selected
                </span>
                <h4 className="text-lg font-extrabold text-green-950">
                  {selectedHospitalName}
                </h4>
              </div>
            </div>

            <div className="flex flex-col items-end">
              <StatusBadge status="awaiting_acceptance" />
              <span className="text-[11px] text-green-700 font-medium mt-1">
                Status: Awaiting Acceptance
              </span>
            </div>
          </div>

          <p className="text-xs text-green-800 bg-white/70 p-3 rounded-lg border border-green-200">
            A transfer package request has been prepared for <strong>{selectedHospitalName}</strong>. Attending physicians and receiving coordinators can track acceptance on the transfer board. Bed capacity will be reserved once accepted.
          </p>
        </div>
      )}

      {/* Hospital Matching Engine Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Building2 className="w-5 h-5 text-primary-600" />
              Recommended Partner Facilities
            </h3>
            <p className="text-xs text-slate-500">
              Ranked deterministically by Required Specialty, Available Beds, and Transit Distance.
            </p>
          </div>

          <Button
            variant="primary"
            leftIcon={<Search className="w-4 h-4" />}
            isLoading={isSearchingMatches}
            disabled={!decision || decision.status !== 'confirmed'}
            onClick={handleFindHospitals}
          >
            {matches.length > 0 ? 'Re-calculate Matches' : 'Find Suitable Hospitals'}
          </Button>
        </div>

        {/* Searching Loading State */}
        {isSearchingMatches && (
          <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col items-center justify-center">
            <Spinner size="lg" />
            <p className="text-sm font-semibold text-slate-800 mt-4">
              Finding suitable receiving hospitals...
            </p>
            <span className="text-xs text-slate-500 mt-1">
              Evaluating specialty alignment, available bed capacities, and transit routes.
            </span>
          </div>
        )}

        {/* Matches Grid */}
        {!isSearchingMatches && matches.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {matches.map((match) => (
              <HospitalMatchCard
                key={match.hospital_id}
                match={match}
                isSelected={transfer?.receiving_hospital_id === match.hospital_id}
                onSelect={handleSelectHospitalClick}
              />
            ))}
          </div>
        )}

        {/* No Matches Controlled State */}
        {!isSearchingMatches && matches.length === 0 && !isLoadingInitial && (
          <div className="p-10 text-center bg-slate-50 rounded-2xl border border-slate-200">
            <Building2 className="w-10 h-10 text-slate-400 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-800">
              No suitable hospital currently has available capacity.
            </h4>
            <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
              Click &quot;Find Suitable Hospitals&quot; to query partner facilities supporting{' '}
              <strong>{decision?.required_specialty || 'the requested specialty'}</strong>.
            </p>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      <HospitalSelectionModal
        isOpen={isModalOpen}
        match={selectedMatchForModal}
        isLoading={isSubmittingSelection}
        onClose={() => setIsModalOpen(false)}
        onConfirm={handleConfirmSelection}
      />
    </div>
  );
};
