import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: string;
  isPositive?: boolean;
  icon?: React.ReactNode;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  change,
  isPositive,
  icon,
}) => {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
        {icon && <div className="text-slate-400 p-1.5 bg-slate-50 rounded-md border border-slate-100">{icon}</div>}
      </div>
      <div className="mt-3 flex items-baseline justify-between">
        <span className="text-2xl font-bold text-slate-900">{value}</span>
        {change && (
          <span className={`text-xs font-medium ${isPositive ? 'text-green-600' : 'text-slate-500'}`}>
            {change}
          </span>
        )}
      </div>
    </div>
  );
};
