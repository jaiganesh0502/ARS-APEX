import React, { useEffect, useState } from 'react';
import { Building, Wifi, WifiOff, Stethoscope } from 'lucide-react';
import { checkSystemHealth } from '../api/health';
import { NotificationBell } from '../components/common/NotificationBell';

export const Header: React.FC = () => {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  const testHealth = async () => {
    try {
      const res = await checkSystemHealth();
      setApiOnline(res.status === 'ok');
    } catch {
      setApiOnline(false);
    }
  };

  useEffect(() => {
    testHealth();
    const interval = setInterval(testHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0">
      {/* Hospital Location */}
      <div className="flex items-center gap-3">
        <div className="p-1.5 bg-slate-100 rounded-md text-slate-600">
          <Building className="w-4 h-4" />
        </div>
        <div>
          <span className="text-sm font-semibold text-slate-800 leading-none block">
            Metro General Hospital
          </span>
          <span className="text-xs text-slate-500">Central Medical Ward & ICU Network</span>
        </div>
      </div>

      {/* Right side status items */}
      <div className="flex items-center gap-4">
        {/* Live Backend API Health Status */}
        <div
          className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${
            apiOnline === true
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : apiOnline === false
              ? 'bg-rose-50 text-rose-700 border-rose-200'
              : 'bg-slate-100 text-slate-600 border-slate-200'
          }`}
          title={apiOnline ? 'FastAPI Backend Online' : 'Backend Unreachable'}
        >
          {apiOnline === true ? (
            <Wifi className="w-3.5 h-3.5 text-emerald-600" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-rose-600" />
          )}
          <span>
            {apiOnline === true
              ? 'API Online'
              : apiOnline === false
              ? 'API Offline'
              : 'Checking API...'}
          </span>
        </div>

        {/* In-App Notification Feed */}
        <NotificationBell />

        {/* Doctor Persona Indicator */}
        <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200">
          <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs border border-blue-200">
            <Stethoscope className="w-4 h-4" />
          </div>
          <div className="text-left">
            <span className="text-xs font-semibold text-slate-900 leading-none block">
              Dr. Aris Thorne
            </span>
            <span className="text-[10px] text-slate-500 font-medium">Attending Physician</span>
          </div>
        </div>
      </div>
    </header>
  );
};
