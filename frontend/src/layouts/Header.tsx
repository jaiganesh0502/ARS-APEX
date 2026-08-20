import React, { useEffect, useState } from 'react';
import { Building, Wifi, WifiOff, Stethoscope, Building2, User as UserIcon, LogOut } from 'lucide-react';
import { checkSystemHealth } from '../api/health';
import { NotificationBell } from '../components/common/NotificationBell';
import { useAuth } from '../context/AuthContext';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();
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

  const getRoleBadge = (role?: string) => {
    switch (role) {
      case 'doctor':
      case 'receiving_doctor':
        return {
          icon: Stethoscope,
          label: 'Attending Physician',
          badgeBg: 'bg-primary-100 text-primary-700 border-primary-200',
        };
      case 'medical_superintendent':
      case 'ward_admin':
      case 'receiving_admin':
        return {
          icon: Building2,
          label: 'Medical Superintendent',
          badgeBg: 'bg-purple-100 text-purple-700 border-purple-200',
        };
      case 'patient':
        return {
          icon: UserIcon,
          label: 'Patient Record',
          badgeBg: 'bg-green-100 text-green-700 border-green-200',
        };
      default:
        return {
          icon: UserIcon,
          label: 'Staff Member',
          badgeBg: 'bg-slate-100 text-slate-700 border-slate-200',
        };
    }
  };

  const roleInfo = getRoleBadge(user?.role);
  const RoleIcon = roleInfo.icon;

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
              ? 'bg-green-50 text-green-700 border-green-200'
              : apiOnline === false
              ? 'bg-red-50 text-red-700 border-red-200'
              : 'bg-slate-100 text-slate-600 border-slate-200'
          }`}
          title={apiOnline ? 'FastAPI Backend Online' : 'Backend Unreachable'}
        >
          {apiOnline === true ? (
            <Wifi className="w-3.5 h-3.5 text-green-600" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-red-600" />
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

        {/* User Profile & Role Indicator */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs border ${roleInfo.badgeBg}`}>
            <RoleIcon className="w-4 h-4" />
          </div>
          <div className="text-left hidden sm:block">
            <span className="text-xs font-semibold text-slate-900 leading-none block">
              {user?.name || 'Authorized Staff'}
            </span>
            <span className="text-[10px] text-slate-500 font-medium">
              {roleInfo.label}
            </span>
          </div>

          {/* Logout Action */}
          <button
            type="button"
            onClick={logout}
            title="Sign Out"
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors ml-1"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
