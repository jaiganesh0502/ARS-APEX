import React from 'react';
import { Badge } from './Badge';
import {
  AdmissionStatus,
  BedStatus,
  DischargeReportStatus,
  TransferStatus,
  AmbulanceStatus,
  ClinicalDecisionStatus,
} from '../../types';

type DomainStatus =
  | AdmissionStatus
  | BedStatus
  | DischargeReportStatus
  | TransferStatus
  | AmbulanceStatus
  | ClinicalDecisionStatus
  | string;

interface StatusBadgeProps {
  status: DomainStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getBadgeVariant = (s: string): 'slate' | 'blue' | 'green' | 'amber' | 'rose' | 'purple' => {
    switch (s) {
      // Positive / Complete states
      case 'approved':
      case 'available':
      case 'completed':
      case 'accepted':
      case 'discharged':
        return 'green';

      // Active / In-progress states
      case 'admitted':
      case 'occupied':
      case 'in_transit':
      case 'en_route':
      case 'patient_onboard':
        return 'blue';

      // Pending / In-review states
      case 'under_review':
      case 'generated':
      case 'transfer_pending':
      case 'matching':
      case 'awaiting_acceptance':
      case 'ambulance_requested':
      case 'requested':
      case 'vacating':
        return 'amber';

      // Cleaning / Maintenance / Draft
      case 'cleaning':
      case 'draft':
      case 'reserved':
        return 'purple';

      // Critical / Rejected / Cancelled
      case 'rejected':
      case 'cancelled':
        return 'rose';

      default:
        return 'slate';
    }
  };

  const formatText = (s: string) => {
    return s.replace(/_/g, ' ').toUpperCase();
  };

  return <Badge variant={getBadgeVariant(status)}>{formatText(status)}</Badge>;
};
