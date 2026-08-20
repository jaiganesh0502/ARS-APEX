import React, { useState, useEffect } from 'react';
import {
  CreditCard,
  CheckCircle2,
  FileText,
  DollarSign,
  Search,
  UserPlus,
  RefreshCw,
} from 'lucide-react';
import { billingApi } from '../api/billing';
import { patientsApi } from '../api/patients';
import { Invoice } from '../types';

export const ReceptionBillingPage: React.FC = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [showPayModal, setShowPayModal] = useState<boolean>(false);
  const [showRegModal, setShowRegModal] = useState<boolean>(false);
  const [showReceiptModal, setShowReceiptModal] = useState<boolean>(false);

  // Payment Form State
  const [payAmount, setPayAmount] = useState<string>('');
  const [payMethod, setPayMethod] = useState<string>('cash');
  const [payRef, setPayRef] = useState<string>('');
  const [payNotes, setPayNotes] = useState<string>('');
  const [processingPay, setProcessingPay] = useState<boolean>(false);
  const [paySuccessMsg, setPaySuccessMsg] = useState<string | null>(null);

  // Registration Form State
  const [regFirstName, setRegFirstName] = useState<string>('');
  const [regLastName, setRegLastName] = useState<string>('');
  const [regCode, setRegCode] = useState<string>('');
  const [regDob, setRegDob] = useState<string>('1990-01-01');
  const [regGender, setRegGender] = useState<string>('Male');
  const [regPhone, setRegPhone] = useState<string>('');
  const [regLoading, setRegLoading] = useState<boolean>(false);

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      const data = await billingApi.listInvoices(statusFilter || undefined);
      setInvoices(data);
    } catch (err) {
      console.error('Failed to load invoices:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, [statusFilter]);

  const handleOpenPayModal = (inv: Invoice) => {
    setSelectedInvoice(inv);
    setPayAmount(inv.balance_amount.toString());
    setPayRef(`RCP-${Date.now().toString().slice(-6)}`);
    setPayMethod('cash');
    setPayNotes('');
    setPaySuccessMsg(null);
    setShowPayModal(true);
  };

  const handleRecordPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoice) return;

    try {
      setProcessingPay(true);
      await billingApi.recordManualPayment(selectedInvoice.id, {
        amount: parseFloat(payAmount),
        payment_method: payMethod,
        reference: payRef,
        notes: payNotes,
      });
      setPaySuccessMsg('Payment recorded successfully! Balance updated.');
      setTimeout(() => {
        setShowPayModal(false);
        fetchInvoices();
      }, 1200);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to record manual payment');
    } finally {
      setProcessingPay(false);
    }
  };

  const handleRegisterPatient = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setRegLoading(true);
      const patientCode = regCode.trim() || `PT-${Math.floor(1000 + Math.random() * 9000)}`;
      await patientsApi.createPatient({
        first_name: regFirstName,
        last_name: regLastName,
        patient_code: patientCode,
        date_of_birth: regDob,
        gender: regGender,
        phone: regPhone || undefined,
      });
      alert(`Patient registered successfully with code ${patientCode}!`);
      setShowRegModal(false);
      setRegFirstName('');
      setRegLastName('');
      setRegCode('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to register patient');
    } finally {
      setRegLoading(false);
    }
  };

  const filteredInvoices = invoices.filter((inv) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      inv.invoice_number.toLowerCase().includes(term) ||
      inv.patient_name?.toLowerCase().includes(term) ||
      inv.patient_code?.toLowerCase().includes(term)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <CreditCard className="w-6 h-6 text-primary-600" />
            Inpatient Reception & Billing Command Center
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage patient registration, itemized hospital invoices, offline receipts, and billing clearance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowRegModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Register Patient
          </button>
          <button
            onClick={fetchInvoices}
            className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg border border-slate-300 transition-colors"
            title="Refresh Invoices"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto">
          {['', 'pending', 'paid_online', 'paid_manual', 'deferred'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg capitalize transition-colors ${
                statusFilter === st
                  ? 'bg-slate-900 text-white'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              {st ? st.replace('_', ' ') : 'All Invoices'}
            </button>
          ))}
        </div>
        <div className="relative w-full sm:w-64">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search invoice or patient..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      </div>

      {/* Invoices Roster Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-700 text-xs uppercase font-semibold border-b border-slate-200">
              <tr>
                <th className="px-6 py-3.5">Invoice #</th>
                <th className="px-6 py-3.5">Patient</th>
                <th className="px-6 py-3.5">Total (₹)</th>
                <th className="px-6 py-3.5">Paid (₹)</th>
                <th className="px-6 py-3.5">Balance (₹)</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                    Loading invoices...
                  </td>
                </tr>
              ) : filteredInvoices.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                    No invoices found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredInvoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 font-mono font-semibold text-primary-700">
                      {inv.invoice_number}
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-900">{inv.patient_name}</div>
                      <div className="text-xs text-slate-500 font-mono">{inv.patient_code}</div>
                    </td>
                    <td className="px-6 py-4 font-semibold text-slate-900">
                      ₹{inv.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4 text-emerald-600 font-medium">
                      ₹{inv.amount_paid.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4 font-bold text-amber-700">
                      ₹{inv.balance_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${
                          inv.payment_status === 'paid_online' || inv.payment_status === 'paid_manual'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : inv.payment_status === 'deferred'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {inv.payment_status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => setSelectedInvoice(inv)}
                        className="px-2.5 py-1 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300"
                      >
                        Breakdown
                      </button>
                      {inv.balance_amount > 0 && inv.payment_status !== 'deferred' && (
                        <button
                          onClick={() => handleOpenPayModal(inv)}
                          className="px-2.5 py-1 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded shadow-sm"
                        >
                          Record Payment
                        </button>
                      )}
                      {(inv.payment_status === 'paid_manual' || inv.payment_status === 'paid_online') && (
                        <button
                          onClick={() => {
                            setSelectedInvoice(inv);
                            setShowReceiptModal(true);
                          }}
                          className="px-2.5 py-1 text-xs font-semibold text-primary-700 bg-primary-50 hover:bg-primary-100 rounded border border-primary-200"
                        >
                          Receipt
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

      {/* Record Offline Payment Modal */}
      {showPayModal && selectedInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-emerald-600" />
                Record Offline Payment
              </h3>
              <button
                onClick={() => setShowPayModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            {paySuccessMsg ? (
              <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm flex items-center gap-2 font-medium">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                {paySuccessMsg}
              </div>
            ) : (
              <form onSubmit={handleRecordPayment} className="space-y-4 text-sm">
                <div>
                  <label className="text-xs font-semibold text-slate-600 uppercase">Patient & Invoice</label>
                  <div className="font-semibold text-slate-900 mt-0.5">
                    {selectedInvoice.patient_name} ({selectedInvoice.patient_code}) — {selectedInvoice.invoice_number}
                  </div>
                  <div className="text-xs text-amber-700 font-bold mt-1">
                    Balance Due: ₹{selectedInvoice.balance_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    Payment Method
                  </label>
                  <select
                    value={payMethod}
                    onChange={(e) => setPayMethod(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="cash">Cash (Counter Collection)</option>
                    <option value="card">Debit / Credit Card (POS Terminal)</option>
                    <option value="upi_manual">Manual UPI (Direct QR / Counter Reference)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    Amount Collected (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={payAmount}
                    onChange={(e) => setPayAmount(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 font-semibold text-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    Receipt / Transaction Reference #
                  </label>
                  <input
                    type="text"
                    required
                    value={payRef}
                    onChange={(e) => setPayRef(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">
                    Cashier Notes (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Paid in cash at reception counter A"
                    value={payNotes}
                    onChange={(e) => setPayNotes(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setShowPayModal(false)}
                    className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium text-sm"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={processingPay}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg shadow transition-colors disabled:opacity-50"
                  >
                    {processingPay ? 'Recording...' : 'Confirm & Issue Receipt'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Invoice Breakdown Modal */}
      {selectedInvoice && !showPayModal && !showReceiptModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-2xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-primary-600" />
                  Itemized Hospital Invoice: {selectedInvoice.invoice_number}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Patient: {selectedInvoice.patient_name} ({selectedInvoice.patient_code})
                </p>
              </div>
              <button
                onClick={() => setSelectedInvoice(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            {/* Line Items Table */}
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-700 uppercase font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-2">Category</th>
                    <th className="px-3 py-2">Description / Reference</th>
                    <th className="px-3 py-2 text-right">Qty</th>
                    <th className="px-3 py-2 text-right">Rate (₹)</th>
                    <th className="px-3 py-2 text-right">Amount (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {selectedInvoice.line_items?.map((li) => (
                    <tr key={li.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2 uppercase font-semibold text-slate-500">{li.category}</td>
                      <td className="px-3 py-2 text-slate-900 font-medium">
                        {li.description}
                        {li.source_reference && (
                          <span className="block text-[10px] text-slate-400 font-normal">
                            {li.source_reference}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right font-mono">{li.quantity}</td>
                      <td className="px-3 py-2 text-right font-mono">₹{li.unit_price.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right font-semibold font-mono text-slate-900">
                        ₹{li.amount.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Calculations Summary */}
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 space-y-1.5 text-xs">
              <div className="flex justify-between text-slate-600">
                <span>Subtotal (Standard ChargeMaster Rates)</span>
                <span className="font-mono font-semibold">₹{selectedInvoice.subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Healthcare Surcharge / GST (5%)</span>
                <span className="font-mono font-semibold">₹{selectedInvoice.tax_amount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm font-bold text-slate-900 pt-2 border-t border-slate-200">
                <span>Total Invoice Amount</span>
                <span className="font-mono">₹{selectedInvoice.total_amount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-emerald-700 font-semibold pt-1">
                <span>Amount Paid</span>
                <span className="font-mono">₹{selectedInvoice.amount_paid.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-amber-700 font-bold text-sm pt-1 border-t border-slate-200">
                <span>Balance Due</span>
                <span className="font-mono">₹{selectedInvoice.balance_amount.toFixed(2)}</span>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setSelectedInvoice(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Patient Registration Modal */}
      {showRegModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-primary-600" />
                New Inpatient Registration
              </h3>
              <button
                onClick={() => setShowRegModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRegisterPatient} className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">First Name</label>
                  <input
                    type="text"
                    required
                    value={regFirstName}
                    onChange={(e) => setRegFirstName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Last Name</label>
                  <input
                    type="text"
                    required
                    value={regLastName}
                    onChange={(e) => setRegLastName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Patient Code (Optional)</label>
                  <input
                    type="text"
                    placeholder="Auto-assigned if blank"
                    value={regCode}
                    onChange={(e) => setRegCode(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Date of Birth</label>
                  <input
                    type="date"
                    required
                    value={regDob}
                    onChange={(e) => setRegDob(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Gender</label>
                  <select
                    value={regGender}
                    onChange={(e) => setRegGender(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Phone Number</label>
                  <input
                    type="tel"
                    placeholder="+91 98765 43210"
                    value={regPhone}
                    onChange={(e) => setRegPhone(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowRegModal(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={regLoading}
                  className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white font-semibold rounded-lg shadow transition-colors disabled:opacity-50"
                >
                  {regLoading ? 'Registering...' : 'Register Patient'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
