import React, { useState, useEffect } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Layers,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { documentsApi } from '../../api/documents';
import { ClinicalDocument, DocumentStatus } from '../../types';

interface ClinicalDocumentUploaderProps {
  admissionId: number;
  onDocumentProcessed?: () => void;
  onUploadSuccess?: (doc: ClinicalDocument) => void;
}

export const ClinicalDocumentUploader: React.FC<ClinicalDocumentUploaderProps> = ({
  admissionId,
  onDocumentProcessed,
  onUploadSuccess,
}) => {
  const [documents, setDocuments] = useState<ClinicalDocument[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [selectedDocType, setSelectedDocType] = useState<string>('doctor_handwritten_notes');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<number | null>(null);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const data = await documentsApi.listDocuments(admissionId);
      setDocuments(data);
    } catch (err) {
      console.error('Failed to load clinical documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (admissionId) {
      fetchDocuments();
    }
  }, [admissionId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setErrorMsg(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setErrorMsg('Please select a clinical source document (PDF or image).');
      return;
    }

    try {
      setUploading(true);
      setErrorMsg(null);
      const uploaded = await documentsApi.uploadDocument(admissionId, selectedFile, selectedDocType);
      setSelectedFile(null);
      await fetchDocuments();
      if (onUploadSuccess) {
        onUploadSuccess(uploaded);
      }
      if (onDocumentProcessed) {
        onDocumentProcessed();
      }
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to upload and process clinical document.');
    } finally {
      setUploading(false);
    }
  };

  const handleRetry = async (docId: number) => {
    try {
      await documentsApi.retryOcr(docId);
      await fetchDocuments();
      if (onDocumentProcessed) {
        onDocumentProcessed();
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to retry OCR');
    }
  };

  const getStatusBadge = (status: DocumentStatus) => {
    switch (status) {
      case 'extraction_completed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" /> Extraction Ready
          </span>
        );
      case 'ocr_completed':
      case 'extraction_processing':
      case 'ocr_processing':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Processing OCR...
          </span>
        );
      case 'ocr_failed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
            <AlertCircle className="w-3.5 h-3.5" /> OCR Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
            Uploaded
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
      <div>
        <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <UploadCloud className="w-5 h-5 text-primary-600" />
          Clinical Source Documents & Automated OCR Pipeline
        </h3>
        <p className="text-xs text-slate-500 mt-1">
          Upload handwritten physician notes, progress sheets, or medication charts. Our OCR pipeline automatically extracts clinical entities and compiles the AI discharge draft.
        </p>
      </div>

      {/* Upload Zone */}
      <div className="p-4 bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-1">
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Document Classification
            </label>
            <select
              value={selectedDocType}
              onChange={(e) => setSelectedDocType(e.target.value)}
              className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            >
              <option value="doctor_handwritten_notes">Doctor Handwritten Notes</option>
              <option value="progress_notes">Clinical Progress Notes</option>
              <option value="treatment_sheet">Treatment Sheet</option>
              <option value="medication_sheet">Medication & Prescription Chart</option>
              <option value="investigation_sheet">Investigation / Lab Results</option>
              <option value="procedure_notes">Operative / Procedure Notes</option>
              <option value="scanned_form">Scanned Admission / Referral Form</option>
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Select Document File (PDF, PNG, JPG)
            </label>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileChange}
              className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
            />
          </div>
        </div>

        {errorMsg && (
          <p className="text-xs text-red-600 font-medium flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" />
            {errorMsg}
          </p>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-slate-200">
          <span className="text-[11px] text-slate-400">
            {selectedFile ? `Selected: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)` : 'Supported formats: PDF, PNG, JPEG up to 15MB'}
          </span>
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
          >
            {uploading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Reading & Extracting...
              </>
            ) : (
              <>
                <UploadCloud className="w-3.5 h-3.5" />
                Upload & Auto-Process
              </>
            )}
          </button>
        </div>
      </div>

      {/* Uploaded Documents List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5" />
            Attached Clinical Records ({documents.length})
          </h4>
          <button
            onClick={fetchDocuments}
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Refresh List
          </button>
        </div>

        {loading ? (
          <p className="text-xs text-slate-400 py-2 text-center">Loading attached records...</p>
        ) : documents.length === 0 ? (
          <p className="text-xs text-slate-400 py-3 text-center bg-slate-50 rounded-lg border border-slate-100">
            No source documents uploaded yet. Upload doctor notes above to auto-generate the discharge draft.
          </p>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="border border-slate-200 rounded-lg p-3 bg-white text-xs space-y-2 hover:border-slate-300 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-primary-600 shrink-0" />
                    <span className="font-semibold text-slate-900 truncate">{doc.file_name}</span>
                    <span className="text-[10px] text-slate-400 font-mono capitalize">
                      ({doc.document_type.replace(/_/g, ' ')})
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {getStatusBadge(doc.ocr_status)}
                    {doc.ocr_confidence && (
                      <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                        {doc.ocr_confidence.toFixed(1)}% Conf
                      </span>
                    )}
                    {doc.ocr_status === 'ocr_failed' && (
                      <button
                        onClick={() => handleRetry(doc.id)}
                        className="px-2 py-0.5 bg-red-100 hover:bg-red-200 text-red-700 rounded text-[11px] font-semibold"
                      >
                        Retry
                      </button>
                    )}
                    <button
                      onClick={() => setExpandedDocId(expandedDocId === doc.id ? null : doc.id)}
                      className="p-1 text-slate-400 hover:text-slate-600 rounded"
                    >
                      {expandedDocId === doc.id ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Expanded OCR Details & Structured Data */}
                {expandedDocId === doc.id && (
                  <div className="mt-2 pt-2 border-t border-slate-100 space-y-2">
                    {doc.ocr_raw_text && (
                      <div>
                        <span className="font-bold text-slate-700 block mb-1">Extracted Raw Text:</span>
                        <pre className="p-2.5 bg-slate-50 rounded border border-slate-200 font-mono text-[11px] text-slate-800 whitespace-pre-wrap max-h-40 overflow-y-auto">
                          {doc.ocr_raw_text}
                        </pre>
                      </div>
                    )}
                    {doc.structured_data && (
                      <div>
                        <span className="font-bold text-slate-700 block mb-1">
                          Structured Clinical Entities:
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded border border-slate-200">
                          {doc.structured_data.medications && (
                            <div>
                              <span className="font-semibold text-primary-800 block">Medications:</span>
                              <ul className="list-disc list-inside text-slate-700 text-[11px]">
                                {doc.structured_data.medications.map((m: any, i: number) => (
                                  <li key={i}>
                                    {typeof m === 'string' ? m : `${m.name} ${m.dose || ''} ${m.frequency || ''}`}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {doc.structured_data.treatments_performed && (
                            <div>
                              <span className="font-semibold text-primary-800 block">Treatments:</span>
                              <ul className="list-disc list-inside text-slate-700 text-[11px]">
                                {doc.structured_data.treatments_performed.map((t: string, i: number) => (
                                  <li key={i}>{t}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
