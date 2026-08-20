import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, ArrowLeft, Home } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';

export const ForbiddenPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleReturnHome = () => {
    if (user?.role === 'patient') {
      navigate('/patient-portal');
    } else {
      navigate('/dashboard');
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-800 border border-slate-700 rounded-xl p-8 text-center shadow-2xl">
        <div className="w-16 h-16 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <ShieldAlert className="w-8 h-8 text-red-400" />
        </div>

        <span className="inline-block px-3 py-1 bg-red-500/20 text-red-300 text-xs font-semibold rounded-full uppercase tracking-wider mb-3">
          403 Access Denied
        </span>

        <h1 className="text-2xl font-bold text-white mb-2">
          Restricted Area
        </h1>

        <p className="text-slate-400 text-sm mb-6 leading-relaxed">
          Your account role <span className="font-mono text-primary-400 font-semibold uppercase">[{user?.role || 'Guest'}]</span> does not have administrative authorization to access this operational route.
        </p>

        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 mb-6 text-left text-xs text-slate-400">
          <div className="font-semibold text-slate-300 mb-1">Role Boundary Policy:</div>
          <ul className="list-disc list-inside space-y-1 text-slate-400">
            <li>Doctors: Clinical decisions, discharge reviews & transfers</li>
            <li>Superintendents: Bed management, billing & fleet operations</li>
            <li>Patients: Personal discharge care plans & records</li>
          </ul>
        </div>

        <div className="flex gap-3 justify-center">
          <Button
            variant="secondary"
            onClick={() => navigate(-1)}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </Button>
          <Button
            variant="primary"
            onClick={handleReturnHome}
            className="flex items-center gap-2"
          >
            <Home className="w-4 h-4" />
            {user?.role === 'patient' ? 'My Care Plan' : 'My Dashboard'}
          </Button>
        </div>
      </div>
    </div>
  );
};
