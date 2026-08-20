import React, { useState } from 'react';
import { Phone } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';

interface HospitalView {
  id: number;
  name: string;
  contact: string;
  distance: string;
  specialties: string[];
  capacities: { specialty: string; available: number; total: number }[];
}

export const HospitalsPage: React.FC = () => {
  const [hospitals] = useState<HospitalView[]>([
    {
      id: 1,
      name: 'Metro General Hospital',
      contact: '+1-415-555-0100',
      distance: '0.0 miles (Current Facility)',
      specialties: ['Cardiology', 'Internal Medicine', 'General Surgery'],
      capacities: [
        { specialty: 'Cardiology', available: 5, total: 20 },
        { specialty: 'General Medicine', available: 8, total: 35 },
      ],
    },
    {
      id: 2,
      name: 'Bay Neurovascular & Trauma Institute',
      contact: '+1-415-555-0200',
      distance: '4.8 miles',
      specialties: ['Neurosurgery', 'Interventional Neuroradiology', 'Trauma 1'],
      capacities: [
        { specialty: 'Neurosurgery ICU', available: 3, total: 12 },
        { specialty: 'Interventional Neuroradiology', available: 2, total: 6 },
      ],
    },
  ]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospital Network & Specialty Capacity"
        description="Regional medical network directory with real-time specialty bed availability for transfers."
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {hospitals.map((h) => (
          <Card key={h.id} title={h.name} subtitle={h.distance}>
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{h.contact}</span>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider block mb-2">
                  Specialties Offered
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {h.specialties.map((spec) => (
                    <Badge key={spec} variant="blue">
                      {spec}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100">
                <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider block mb-2">
                  Live Bed Capacity
                </span>
                <div className="space-y-2">
                  {h.capacities.map((cap) => (
                    <div
                      key={cap.specialty}
                      className="p-2.5 bg-slate-50 rounded-md border border-slate-100 flex items-center justify-between text-xs"
                    >
                      <span className="font-medium text-slate-800">{cap.specialty}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-emerald-700">
                          {cap.available} Available
                        </span>
                        <span className="text-slate-400">/ {cap.total} Total</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
