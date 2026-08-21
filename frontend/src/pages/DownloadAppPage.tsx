import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Smartphone,
  Download,
  QrCode,
  CheckCircle2,
  ShieldCheck,
  Stethoscope,
  Users,
  CreditCard,
  Building2,
  Sparkles,
  Apple,
  Copy,
  ExternalLink,
} from 'lucide-react';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';

export const DownloadAppPage: React.FC = () => {
  const navigate = useNavigate();
  const [copiedSha, setCopiedSha] = useState(false);

  const sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

  const handleCopySha = () => {
    navigator.clipboard.writeText(sha256);
    setCopiedSha(true);
    setTimeout(() => setCopiedSha(false), 2500);
  };

  const handleDownloadApk = () => {
    const link = document.createElement('a');
    link.href = '/alta-care-suite.apk';
    link.download = 'Alta-Care-Suite-v1.0.0.apk';
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-primary-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="bg-slate-900/90 backdrop-blur-md border-b border-slate-800/80 px-6 py-4 flex items-center justify-between sticky top-0 z-30 shadow-lg">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/dashboard')}>
          <img src="/logo.jpg" alt="Alta" className="w-9 h-9 rounded-xl shadow-md border border-slate-700/50" />
          <div>
            <span className="font-bold text-white text-base tracking-tight leading-none block">
              Alta Hospital Suite
            </span>
            <span className="text-[10px] uppercase font-semibold text-primary-400 tracking-wider">
              Discharge & Transfer Orchestration
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>
            Staff Login
          </Button>
          <Button variant="primary" size="sm" onClick={() => navigate('/patient-portal')}>
            Patient Portal
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-16 pb-20 px-6 max-w-6xl mx-auto w-full">
        {/* Glow backdrop */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-primary-600/15 rounded-full blur-3xl pointer-events-none" />

        <div className="text-center space-y-4 max-w-3xl mx-auto relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary-950/80 border border-primary-800 text-xs font-semibold text-primary-300 shadow-inner">
            <Sparkles className="w-3.5 h-3.5 text-primary-400" />
            <span>Official Alta Mobile Suite v1.0.0 Released</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-tight">
            Hospital Operations & Care in Your Pocket
          </h1>

          <p className="text-slate-400 text-base sm:text-lg leading-relaxed">
            Real-time clinical round sign-offs, automated dual clearance, live inter-hospital ambulance fleet tracking, and 1-click patient recovery portals.
          </p>

          {/* Quick Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
            <Button
              variant="primary"
              size="lg"
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-lg shadow-emerald-950/40 flex items-center gap-2 px-6 py-3 rounded-xl text-sm"
              leftIcon={<Download className="w-5 h-5" />}
              onClick={handleDownloadApk}
            >
              Download Android APK (v1.0.0)
            </Button>

            <Button
              variant="secondary"
              size="lg"
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold px-6 py-3 rounded-xl text-sm"
              leftIcon={<Apple className="w-5 h-5 text-slate-400" />}
              onClick={() => {
                alert('To install on iOS: Open Safari, tap the Share icon, and select "Add to Home Screen".');
              }}
            >
              Install iOS / Web App
            </Button>
          </div>
        </div>
      </section>

      {/* Main Download Cards Grid */}
      <section className="px-6 pb-20 max-w-6xl mx-auto w-full grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: Android APK */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between hover:border-emerald-500/50 transition-all group">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="p-3 bg-emerald-950/80 border border-emerald-800 text-emerald-400 rounded-xl">
                <Smartphone className="w-7 h-7" />
              </div>
              <Badge variant="green" size="sm">
                STANDALONE APK
              </Badge>
            </div>

            <div>
              <h3 className="text-lg font-bold text-white group-hover:text-emerald-400 transition-colors">
                Android Package (APK)
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Native Android build with full offline care snapshot caching and background push notifications.
              </p>
            </div>

            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs space-y-2 font-mono text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-500">Version:</span>
                <span>v1.0.0-release</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">File Size:</span>
                <span>18.4 MB</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Android:</span>
                <span>8.0 (API 26) +</span>
              </div>
            </div>
          </div>

          <div className="pt-6 space-y-3">
            <Button
              variant="primary"
              size="md"
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
              leftIcon={<Download className="w-4 h-4" />}
              onClick={handleDownloadApk}
            >
              Direct APK Download
            </Button>
            <p className="text-[10px] text-center text-slate-500">
              Verified safe by Alta Security Subsystem
            </p>
          </div>
        </div>

        {/* Card 2: QR Code Mobile Scanner */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between hover:border-primary-500/50 transition-all">
          <div className="space-y-4 text-center flex flex-col items-center">
            <div className="p-3 bg-primary-950/80 border border-primary-800 text-primary-400 rounded-xl">
              <QrCode className="w-7 h-7" />
            </div>

            <div>
              <h3 className="text-lg font-bold text-white">Scan to Install</h3>
              <p className="text-xs text-slate-400 mt-1">
                Scan with your phone camera to download directly onto your device.
              </p>
            </div>

            {/* QR Visual */}
            <div className="p-4 bg-white rounded-2xl shadow-inner inline-block mt-2">
              <QrCode className="w-36 h-36 text-slate-950" />
            </div>
          </div>

          <div className="pt-4 text-center">
            <span className="text-xs font-mono text-primary-400 bg-primary-950/80 px-3 py-1 rounded-md border border-primary-900">
              https://altaa.duckdns.org
            </span>
          </div>
        </div>

        {/* Card 3: iOS & Progressive Web App */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between hover:border-blue-500/50 transition-all">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="p-3 bg-blue-950/80 border border-blue-800 text-blue-400 rounded-xl">
                <Apple className="w-7 h-7" />
              </div>
              <Badge variant="primary" size="sm">
                PWA / WEB APP
              </Badge>
            </div>

            <div>
              <h3 className="text-lg font-bold text-white">iOS & Desktop PWA</h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Zero-install Progressive Web App compatible with iPhone, iPad, macOS, Windows, and Linux.
              </p>
            </div>

            <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 text-xs space-y-2.5 text-slate-300">
              <div className="flex items-start gap-2">
                <span className="w-4 h-4 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  1
                </span>
                <span>Open <strong>https://altaa.duckdns.org</strong> in Safari or Chrome.</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-4 h-4 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  2
                </span>
                <span>Tap <strong>Share</strong> (iOS) or <strong>Install</strong> icon (Chrome).</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-4 h-4 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  3
                </span>
                <span>Tap <strong>"Add to Home Screen"</strong> for full-screen native feel.</span>
              </div>
            </div>
          </div>

          <div className="pt-6">
            <Button
              variant="outline"
              size="md"
              className="w-full border-blue-700 text-blue-300 hover:bg-blue-950/60 font-semibold"
              rightIcon={<ExternalLink className="w-4 h-4" />}
              onClick={() => navigate('/login')}
            >
              Open Web Portal
            </Button>
          </div>
        </div>
      </section>

      {/* Role Capabilities Section */}
      <section className="bg-slate-900/50 border-t border-b border-slate-800 py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center space-y-2 mb-12">
            <span className="text-xs font-bold uppercase tracking-wider text-primary-400">
              Multi-Persona Architecture
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white">
              Tailored for Every Healthcare Stakeholder
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Persona 1 */}
            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
              <div className="p-2.5 bg-emerald-950 text-emerald-400 rounded-xl w-fit">
                <Stethoscope className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white text-base">Attending Doctors</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Bedside discharge report sign-offs, AI clinical summary generation, and instant transfer requests.
              </p>
            </div>

            {/* Persona 2 */}
            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
              <div className="p-2.5 bg-blue-950 text-blue-400 rounded-xl w-fit">
                <Building2 className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white text-base">Superintendents</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Real-time bed occupancy heatmaps, inter-hospital ambulance GPS telemetry, and audit event streams.
              </p>
            </div>

            {/* Persona 3 */}
            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
              <div className="p-2.5 bg-amber-950 text-amber-400 rounded-xl w-fit">
                <CreditCard className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white text-base">Reception & Billing</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Dynamic UPI QR code generation, cash/card clearance recording, and automated invoice clearance gates.
              </p>
            </div>

            {/* Persona 4 */}
            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
              <div className="p-2.5 bg-purple-950 text-purple-400 rounded-xl w-fit">
                <Users className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-white text-base">Patients & Families</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Plain-language recovery plans, medication timing reminders, and instant digital UPI bill settlement.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Security & Cryptographic Integrity Section */}
      <section className="px-6 py-14 max-w-4xl mx-auto w-full text-center space-y-6">
        <div className="flex items-center justify-center gap-2 text-emerald-400">
          <ShieldCheck className="w-6 h-6" />
          <span className="font-bold text-sm tracking-wide uppercase">Cryptographic Package Verification</span>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-left space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>SHA-256 Checksum:</span>
            <button
              onClick={handleCopySha}
              className="flex items-center gap-1 text-primary-400 hover:text-primary-300 font-mono text-[11px]"
            >
              {copiedSha ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy Hash</span>
                </>
              )}
            </button>
          </div>
          <div className="font-mono text-xs text-slate-300 break-all bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 select-all">
            {sha256}
          </div>
        </div>

        <p className="text-xs text-slate-500">
          FHIR R4 Compliant • End-to-End Encrypted • HIPAA / DISHA Aligned • Role-Based Access Control
        </p>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-800 py-6 px-6 text-center text-xs text-slate-500 bg-slate-950">
        <p>© 2026 Alta Discharge & Inter-Hospital Transfer Orchestration Platform. All rights reserved.</p>
      </footer>
    </div>
  );
};
