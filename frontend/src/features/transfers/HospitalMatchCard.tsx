import React from 'react';
import { Building2, BedDouble, Navigation, CheckCircle2, ShieldAlert, Sparkles } from 'lucide-react';
import { HospitalMatch } from '../../types';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';

interface HospitalMatchCardProps {
  match: HospitalMatch;
  isSelected?: boolean;
  onSelect: (match: HospitalMatch) => void;
  disabled?: boolean;
}

export const HospitalMatchCard: React.FC<HospitalMatchCardProps> = ({
  match,
  isSelected = false,
  onSelect,
  disabled = false,
}) => {
  return (
    <div
      className={`relative rounded-xl border transition-all p-5 bg-white shadow-sm flex flex-col justify-between ${
        isSelected
          ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-50/30'
          : match.is_recommended
          ? 'border-blue-300 shadow-md ring-1 ring-blue-500/10'
          : 'border-slate-200 hover:border-slate-300 hover:shadow'
      }`}
    >
      {/* Recommended Pill */}
      {match.is_recommended && !isSelected && (
        <div className="absolute -top-3 left-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-bold bg-blue-600 text-white shadow-sm tracking-wide">
            <Sparkles className="w-3 h-3" /> RECOMMENDED
          </span>
        </div>
      )}

      {isSelected && (
        <div className="absolute -top-3 left-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-bold bg-emerald-600 text-white shadow-sm tracking-wide">
            <CheckCircle2 className="w-3 h-3" /> SELECTED FACILITY
          </span>
        </div>
      )}

      <div>
        {/* Header with Title & Score */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-slate-500 shrink-0" />
              {match.hospital_name}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Contact: {match.contact_number}</p>
          </div>

          <div className="flex flex-col items-end">
            <div className="flex items-baseline gap-0.5">
              <span className="text-2xl font-black text-slate-900">{match.match_score}</span>
              <span className="text-xs text-slate-400 font-semibold">/100</span>
            </div>
            <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
              Match Score
            </span>
          </div>
        </div>

        {/* Vital Facility Stats */}
        <div className="grid grid-cols-3 gap-2 my-3 p-2.5 bg-slate-50 rounded-lg border border-slate-100 text-xs">
          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-medium">Specialty</span>
            <span className="font-semibold text-blue-700 truncate block mt-0.5">
              {match.required_specialty}
            </span>
          </div>

          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-medium flex items-center gap-1">
              <BedDouble className="w-3 h-3 text-slate-400" /> Availability
            </span>
            <span
              className={`font-semibold block mt-0.5 ${
                match.available_beds > 0 ? 'text-emerald-700' : 'text-rose-600'
              }`}
            >
              {match.available_beds} {match.available_beds === 1 ? 'bed' : 'beds'} free
            </span>
          </div>

          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-medium flex items-center gap-1">
              <Navigation className="w-3 h-3 text-slate-400" /> Distance
            </span>
            <span className="font-semibold text-slate-800 block mt-0.5">
              {match.distance_km} km
            </span>
          </div>
        </div>

        {/* Explainable Reasons */}
        <div className="my-3">
          <span className="text-xs font-semibold text-slate-700 block mb-1.5">
            Why Recommended:
          </span>
          <ul className="space-y-1 text-xs text-slate-600">
            {match.match_reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="text-emerald-500 font-bold shrink-0">•</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Action Footer */}
      <div className="pt-3 mt-2 border-t border-slate-100 flex items-center justify-between">
        {match.emergency && (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-700">
            <ShieldAlert className="w-3.5 h-3.5" /> Fast-track priority
          </span>
        )}

        <div className="ml-auto">
          {isSelected ? (
            <Badge variant="green" size="md">
              Selected
            </Badge>
          ) : (
            <Button
              variant={match.is_recommended ? 'primary' : 'outline'}
              size="sm"
              disabled={disabled || match.available_beds <= 0}
              onClick={() => onSelect(match)}
            >
              Select Hospital
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
