import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  BedDouble,
  ArrowRightLeft,
  Inbox,
  Building2,
  Ambulance,
  Cpu,
  FileHeart,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Sidebar: React.FC = () => {
  const { user } = useAuth();
  const role = user?.role;

  const getNavigationItems = () => {
    if (role === 'patient') {
      return [
        { name: 'My Care Plan & Summary', href: '/patient-portal', icon: FileHeart },
      ];
    }

    if (role === 'medical_superintendent' || role === 'ward_admin' || role === 'receiving_admin') {
      return [
        { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
        { name: 'Operations & Events', href: '/operations', icon: Cpu },
        { name: 'Patients', href: '/patients', icon: Users },
        { name: 'Beds', href: '/beds', icon: BedDouble },
        { name: 'Transfers', href: '/transfers', icon: ArrowRightLeft },
        { name: 'Incoming Transfers', href: '/receiving/transfers', icon: Inbox },
        { name: 'Hospitals', href: '/hospitals', icon: Building2 },
        { name: 'Ambulances', href: '/ambulances', icon: Ambulance },
      ];
    }

    // Doctor navigation (Clinical only)
    return [
      { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
      { name: 'Patients', href: '/patients', icon: Users },
      { name: 'Transfers', href: '/transfers', icon: ArrowRightLeft },
    ];
  };

  const navigation = getNavigationItems();

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 shrink-0">
      {/* Brand & Logo */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800 bg-slate-950">
        <img src="/logo.jpg" alt="Alta" className="w-9 h-9 rounded-lg shrink-0" />
        <div>
          <span className="font-bold text-white text-base tracking-tight leading-none block">
            MedOrchestrate
          </span>
          <span className="text-[10px] uppercase font-semibold text-primary-400 tracking-wider">
            Discharge & Transfer
          </span>
        </div>
      </div>

      {/* Navigation links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navigation.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-700 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`
              }
            >
              <Icon className="w-5 h-5 shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Role-Specific System Status Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/50 text-xs text-slate-400">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          <span className="font-semibold text-slate-300">
            {role === 'medical_superintendent'
              ? 'Superintendent View'
              : role === 'patient'
              ? 'Patient Care Portal'
              : 'Physician Authority'}
          </span>
        </div>
        <p className="text-[11px] text-slate-500 leading-tight">
          {role === 'medical_superintendent'
            ? 'Bed release & operational tracking active.'
            : role === 'patient'
            ? 'Access your personalized recovery instructions.'
            : 'Physician sign-off required for discharge.'}
        </p>
      </div>
    </aside>
  );
};
