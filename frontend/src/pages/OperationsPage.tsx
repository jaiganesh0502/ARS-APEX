import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Clock,
  Send,
  Cpu,
  Layers,
  Eye,
  X,
  FileText,
  ShieldCheck,
} from 'lucide-react';
import { workflowsApi } from '../api/workflows';
import type { WorkflowEvent, WorkflowDashboardCounts } from '../types';

export const OperationsPage: React.FC = () => {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [counts, setCounts] = useState<WorkflowDashboardCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState<'all' | 'delivery_failed' | 'orch_failed' | 'discharges' | 'transfers' | 'billing'>('all');
  const [selectedEvent, setSelectedEvent] = useState<WorkflowEvent | null>(null);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      const [countsData, eventsData] = await Promise.all([
        workflowsApi.getWorkflowDashboardCounts(),
        workflowsApi.listWorkflowEvents({ limit: 100 }),
      ]);
      setCounts(countsData);
      setEvents(eventsData);
    } catch (err) {
      console.error('Failed to load workflow operations data', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 15000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const handleRetry = async (eventId: number) => {
    try {
      setRetryingId(eventId);
      setActionMessage(null);
      const res = await workflowsApi.retryWorkflowEvent(eventId);
      setActionMessage(`Event #${res.event_id} delivery status: ${res.delivery_status}`);
      await fetchDashboardData();
    } catch (err: any) {
      setActionMessage(`Retry failed: ${err.response?.data?.error?.message || err.message}`);
    } finally {
      setRetryingId(null);
    }
  };

  const filteredEvents = events.filter((evt) => {
    if (filterTab === 'delivery_failed') return evt.delivery_status === 'failed';
    if (filterTab === 'orch_failed') return evt.orchestration_status === 'failed';
    if (filterTab === 'discharges') return evt.event_type.includes('discharge') || evt.event_type.includes('report');
    if (filterTab === 'transfers') return evt.event_type.includes('transfer') || evt.event_type.includes('ambulance') || evt.event_type.includes('hospital');
    if (filterTab === 'billing') return evt.event_type.includes('billing');
    return true;
  });

  const getDeliveryBadge = (status: string) => {
    switch (status) {
      case 'delivered':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 mr-1" /> Delivered
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
            <AlertTriangle className="w-3 h-3 mr-1" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            <Clock className="w-3 h-3 mr-1" /> Pending
          </span>
        );
    }
  };

  const getOrchestrationBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3 mr-1" /> Completed
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-300">
            <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> In-Progress
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-300">
            <AlertTriangle className="w-3 h-3 mr-1" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            <Clock className="w-3 h-3 mr-1" /> Queued
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Activity className="w-7 h-7 text-indigo-600" />
            Operations & Workflow Orchestration
          </h1>
          <p className="text-slate-600 mt-1">
            Real-time telemetry for domain event webhooks, n8n orchestrations, and internal API actions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="inline-flex items-center px-3.5 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 transition shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 mr-2 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
            Refresh Telemetry
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 px-4 py-3 rounded-lg text-sm flex items-center justify-between shadow-sm">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-indigo-600 hover:text-indigo-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* KPI Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Events</span>
            <Layers className="w-5 h-5 text-indigo-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{counts?.total_events || 0}</p>
          <span className="text-xs text-slate-500 mt-1 block">Recorded in database</span>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Webhook Delivery</span>
            <Send className="w-5 h-5 text-emerald-600" />
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <p className="text-2xl font-bold text-emerald-600">{counts?.delivery_delivered || 0}</p>
            <span className="text-xs text-slate-500">/ {counts?.delivery_failed || 0} failed</span>
          </div>
          <span className="text-xs text-slate-500 mt-1 block">{counts?.delivery_pending || 0} pending transmission</span>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Orchestrations</span>
            <Cpu className="w-5 h-5 text-blue-600" />
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <p className="text-2xl font-bold text-blue-600">{counts?.orchestration_completed || 0}</p>
            <span className="text-xs text-slate-500">completed</span>
          </div>
          <span className="text-xs text-slate-500 mt-1 block">{counts?.orchestration_processing || 0} active in n8n</span>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Action Needed</span>
            <AlertTriangle className="w-5 h-5 text-rose-500" />
          </div>
          <p className="text-2xl font-bold text-rose-600 mt-2">
            {(counts?.delivery_failed || 0) + (counts?.orchestration_failed || 0)}
          </p>
          <span className="text-xs text-slate-500 mt-1 block">Failed deliveries or workflows</span>
        </div>
      </div>

      {/* Tabs & Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="border-b border-slate-200 px-6 py-3 flex flex-wrap gap-2 items-center bg-slate-50/70">
          <button
            onClick={() => setFilterTab('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              filterTab === 'all' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200/60'
            }`}
          >
            All Events ({events.length})
          </button>
          <button
            onClick={() => setFilterTab('delivery_failed')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              filterTab === 'delivery_failed' ? 'bg-red-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200/60'
            }`}
          >
            Delivery Failed ({events.filter((e) => e.delivery_status === 'failed').length})
          </button>
          <button
            onClick={() => setFilterTab('orch_failed')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              filterTab === 'orch_failed' ? 'bg-rose-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200/60'
            }`}
          >
            Orchestration Failed ({events.filter((e) => e.orchestration_status === 'failed').length})
          </button>
          <button
            onClick={() => setFilterTab('discharges')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              filterTab === 'discharges' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200/60'
            }`}
          >
            Discharges
          </button>
          <button
            onClick={() => setFilterTab('transfers')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              filterTab === 'transfers' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200/60'
            }`}
          >
            Transfers
          </button>
          <button
            onClick={() => setFilterTab('billing')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              filterTab === 'billing' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200/60'
            }`}
          >
            Billing Clearance
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">Event ID</th>
                <th className="px-6 py-3">Event Type</th>
                <th className="px-6 py-3">Entity Reference</th>
                <th className="px-6 py-3">Delivery Status</th>
                <th className="px-6 py-3">Orchestration</th>
                <th className="px-6 py-3">Attempts</th>
                <th className="px-6 py-3">Created At</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-slate-400">
                    No workflow events found for the selected filter.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((event) => (
                  <tr key={event.id} className="hover:bg-slate-50/80 transition">
                    <td className="px-6 py-3.5 font-mono text-xs text-slate-500">#{event.id}</td>
                    <td className="px-6 py-3.5 font-medium text-slate-900 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                      {event.event_type}
                    </td>
                    <td className="px-6 py-3.5 text-xs text-slate-600">
                      <span className="font-semibold text-slate-700">{event.entity_type}</span> ID: {event.entity_id}
                    </td>
                    <td className="px-6 py-3.5">{getDeliveryBadge(event.delivery_status)}</td>
                    <td className="px-6 py-3.5">{getOrchestrationBadge(event.orchestration_status)}</td>
                    <td className="px-6 py-3.5 text-xs text-slate-500">{event.attempt_count}</td>
                    <td className="px-6 py-3.5 text-xs text-slate-500">
                      {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="px-6 py-3.5 text-right space-x-2">
                      <button
                        onClick={() => setSelectedEvent(event)}
                        className="inline-flex items-center px-2.5 py-1 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded transition"
                        title="View Diagnostic Payload"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" /> Inspect
                      </button>
                      {(event.delivery_status === 'failed' || event.orchestration_status === 'failed') && (
                        <button
                          onClick={() => handleRetry(event.id)}
                          disabled={retryingId === event.id}
                          className="inline-flex items-center px-2.5 py-1 text-xs font-medium text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded transition"
                          title="Retry Webhook Delivery"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 mr-1 ${retryingId === event.id ? 'animate-spin' : ''}`} />
                          Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Diagnostic Inspection Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-600" />
                <h3 className="font-semibold text-slate-900">
                  Workflow Event Diagnostic #{selectedEvent.id}
                </h3>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-slate-600 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4 bg-slate-50 p-4 rounded-xl border border-slate-100">
                <div>
                  <span className="text-xs text-slate-400 uppercase font-semibold">Event Type</span>
                  <p className="font-mono font-medium text-slate-900 mt-0.5">{selectedEvent.event_type}</p>
                </div>
                <div>
                  <span className="text-xs text-slate-400 uppercase font-semibold">Entity Reference</span>
                  <p className="text-slate-900 mt-0.5">{selectedEvent.entity_type} (ID: {selectedEvent.entity_id})</p>
                </div>
                <div>
                  <span className="text-xs text-slate-400 uppercase font-semibold">Delivery State</span>
                  <div className="mt-1">{getDeliveryBadge(selectedEvent.delivery_status)}</div>
                </div>
                <div>
                  <span className="text-xs text-slate-400 uppercase font-semibold">Orchestration State</span>
                  <div className="mt-1">{getOrchestrationBadge(selectedEvent.orchestration_status)}</div>
                </div>
              </div>

              {selectedEvent.last_error && (
                <div className="bg-rose-50 border border-rose-200 text-rose-800 p-3 rounded-lg text-xs">
                  <span className="font-bold block mb-1">Last Error Trace:</span>
                  {selectedEvent.last_error}
                </div>
              )}

              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                  Event JSON Payload (FastAPI $\to$ n8n)
                </span>
                <pre className="bg-slate-900 text-emerald-400 p-4 rounded-xl text-xs overflow-x-auto font-mono">
                  {JSON.stringify(selectedEvent.payload, null, 2)}
                </pre>
              </div>

              <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-50 p-3 rounded-lg border border-slate-100">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Payload secured by HMAC header signature (X-Workflow-Secret). Clinical data is non-blocking.</span>
              </div>
            </div>

            <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end gap-2">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
