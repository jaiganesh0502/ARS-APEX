import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ActivitySquare, ShieldCheck } from 'lucide-react';
import { Button } from '../components/common/Button';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden">
        <div className="p-8 text-center bg-slate-950 text-white">
          <div className="inline-flex p-3 bg-blue-600 rounded-xl mb-4">
            <ActivitySquare className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold tracking-tight">MedOrchestrate</h2>
          <p className="text-xs text-slate-400 mt-1">
            Hospital Discharge & Inter-Hospital Transfer System
          </p>
        </div>

        <form onSubmit={handleLogin} className="p-8 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Clinician ID / Email
            </label>
            <input
              type="email"
              defaultValue="dr.thorne@hospital.local"
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-md text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Passcode / Token
            </label>
            <input
              type="password"
              defaultValue="••••••••"
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-md text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
              required
            />
          </div>

          <div className="p-3 bg-blue-50 border border-blue-100 rounded-md flex items-start gap-2.5 text-xs text-blue-800">
            <ShieldCheck className="w-4 h-4 shrink-0 text-blue-600 mt-0.5" />
            <span>
              Authentication placeholder. Role: <strong>Attending Physician (Doctor)</strong>
            </span>
          </div>

          <Button type="submit" variant="primary" className="w-full py-2.5">
            Sign In to Clinical Portal
          </Button>
        </form>
      </div>
    </div>
  );
};
