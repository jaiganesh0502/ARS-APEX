import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  CreditCard,
  ShieldCheck,
  Stethoscope,
  Building2,
  User as UserIcon,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, user } = useAuth();

  const [email, setEmail] = useState('doctor@demo.local');
  const [password, setPassword] = useState('DoctorDemo123!');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect
  React.useEffect(() => {
    if (isAuthenticated && user) {
      const from = (location.state as any)?.from?.pathname;
      if (from && from !== '/login') {
        navigate(from, { replace: true });
      } else if (user.role === 'patient') {
        navigate('/patient-portal', { replace: true });
      } else if (user.role === 'medical_superintendent') {
        navigate('/operations', { replace: true });
      } else {
        navigate('/dashboard', { replace: true });
      }
    }
  }, [isAuthenticated, user, navigate, location.state]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const loggedUser = await login(email, password);
      const from = (location.state as any)?.from?.pathname;
      if (from && from !== '/login') {
        navigate(from, { replace: true });
      } else if (loggedUser.role === 'patient') {
        navigate('/patient-portal', { replace: true });
      } else if (loggedUser.role === 'medical_superintendent') {
        navigate('/operations', { replace: true });
      } else {
        navigate('/dashboard', { replace: true });
      }
    } catch (err: any) {
      const msg =
        err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        'Invalid credentials. Please verify your email and password.';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const setDemoPreset = (presetEmail: string, presetPass: string) => {
    setEmail(presetEmail);
    setPassword(presetPass);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <img
          src="/logo.jpg"
          alt="Alta"
          className="inline-block w-16 h-16 rounded-2xl shadow-lg shadow-primary-500/20 mb-4 ring-1 ring-white/10"
        />
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Alta
        </h1>
        <p className="mt-1.5 text-xs text-slate-400 font-medium tracking-wide uppercase">
          AI Hospital Discharge & Inter-Hospital Transfer System
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden p-6 sm:p-8">
          {error && (
            <div className="mb-6 p-4 bg-red-950/60 border border-red-800/80 rounded-xl flex items-start gap-3 text-xs text-red-200">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Hospital ID / Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="staff@demo.local"
                className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent pr-10 transition-all"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              disabled={isSubmitting}
              className="w-full py-2.5 flex items-center justify-center gap-2 mt-2 bg-primary-600 hover:bg-primary-500 text-white font-medium rounded-lg shadow-sm transition-all"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </Button>
          </form>

          {/* Quick-fill 1-Click Demo Accounts */}
          <div className="mt-8 pt-6 border-t border-slate-800">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-3 text-center">
              Quick-Fill Demo Persona Presets
            </p>
            <div className="grid grid-cols-1 gap-2.5">
              {/* Doctor Preset */}
              <button
                type="button"
                onClick={() => setDemoPreset('doctor@demo.local', 'DoctorDemo123!')}
                className="flex items-center justify-between p-2.5 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-primary-950/30 hover:border-primary-700/50 text-left transition-all group"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 bg-primary-600/20 text-primary-400 rounded-md group-hover:bg-primary-600 group-hover:text-white transition-colors">
                    <Stethoscope className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-200">Attending Physician (Doctor)</div>
                    <div className="text-[11px] text-slate-400">doctor@demo.local</div>
                  </div>
                </div>
                <span className="text-[10px] font-medium bg-primary-900/60 text-primary-300 px-2 py-0.5 rounded border border-primary-700/50">
                  Clinical Sign-Off
                </span>
              </button>

              {/* Medical Superintendent Preset */}
              <button
                type="button"
                onClick={() => setDemoPreset('superintendent@demo.local', 'SuperDemo123!')}
                className="flex items-center justify-between p-2.5 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-purple-950/30 hover:border-purple-700/50 text-left transition-all group"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 bg-purple-600/20 text-purple-400 rounded-md group-hover:bg-purple-600 group-hover:text-white transition-colors">
                    <Building2 className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-200">Sending Superintendent (Command Center)</div>
                    <div className="text-[11px] text-slate-400">superintendent@demo.local</div>
                  </div>
                </div>
                <span className="text-[10px] font-medium bg-purple-900/60 text-purple-300 px-2 py-0.5 rounded border border-purple-700/50">
                  Sending Operations
                </span>
              </button>

              {/* Receiving Hospital Doctor / MS Preset */}
              <button
                type="button"
                onClick={() => setDemoPreset('receiving_doctor@demo.local', 'ReceivingDemo123!')}
                className="flex items-center justify-between p-2.5 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-teal-950/30 hover:border-teal-700/50 text-left transition-all group"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 bg-teal-600/20 text-teal-400 rounded-md group-hover:bg-teal-600 group-hover:text-white transition-colors">
                    <Stethoscope className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-200">Receiving Doctor / MS (Dr. Elena)</div>
                    <div className="text-[11px] text-slate-400">receiving_doctor@demo.local</div>
                  </div>
                </div>
                <span className="text-[10px] font-medium bg-teal-900/60 text-teal-300 px-2 py-0.5 rounded border border-teal-700/50">
                  Accept Transfer & Bed
                </span>
              </button>

              {/* Receptionist Preset */}
              <button
                type="button"
                onClick={() => setDemoPreset('receptionist@demo.local', 'ReceptionDemo123!')}
                className="flex items-center justify-between p-2.5 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-amber-950/30 hover:border-amber-700/50 text-left transition-all group"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 bg-amber-600/20 text-amber-400 rounded-md group-hover:bg-amber-600 group-hover:text-white transition-colors">
                    <CreditCard className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-200">Hospital Receptionist (Priya)</div>
                    <div className="text-[11px] text-slate-400">receptionist@demo.local</div>
                  </div>
                </div>
                <span className="text-[10px] font-medium bg-amber-900/60 text-amber-300 px-2 py-0.5 rounded border border-amber-700/50">
                  Registration & Invoices
                </span>
              </button>

              {/* Patient Demo Preset */}
              <button
                type="button"
                onClick={() => setDemoPreset('patient@demo.local', 'PatientDemo123!')}
                className="flex items-center justify-between p-2.5 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-green-950/30 hover:border-green-700/50 text-left transition-all group"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 bg-green-600/20 text-green-400 rounded-md group-hover:bg-green-600 group-hover:text-white transition-colors">
                    <UserIcon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-200">Patient (Arun Kumar)</div>
                    <div className="text-[11px] text-slate-400">patient@demo.local</div>
                  </div>
                </div>
                <span className="text-[10px] font-medium bg-green-900/60 text-green-300 px-2 py-0.5 rounded border border-green-700/50">
                  Care Portal & Bill Pay
                </span>
              </button>
            </div>
          </div>

          <div className="mt-6 flex items-center justify-center gap-2 text-[11px] text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5 text-green-400" />
            <span>JWT Bearer RBAC Active with bcrypt encryption</span>
          </div>
        </div>
      </div>
    </div>
  );
};
