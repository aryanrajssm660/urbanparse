import { useState, useEffect } from 'react';
import type { Address, AddressStatus, AddressUpdate } from '../types/address';
import { updateAddress, reparseAddress } from '../api/client';
import StatusBadge from './StatusBadge';

interface AddressDetailProps {
  address: Address;
  onClose: () => void;
  onUpdated: (address: Address) => void;
}

const EDITABLE_FIELDS: { key: keyof AddressUpdate; label: string }[] = [
  { key: 'house', label: 'House / Flat' },
  { key: 'street', label: 'Street' },
  { key: 'locality', label: 'Locality' },
  { key: 'city', label: 'City' },
  { key: 'state', label: 'State' },
  { key: 'pin', label: 'PIN Code' },
];

const STATUS_OPTIONS: AddressStatus[] = ['PARSED', 'NEEDS_REVIEW', 'UNPARSEABLE', 'ERROR'];

export default function AddressDetail({ address, onClose, onUpdated }: AddressDetailProps) {
  const [fields, setFields] = useState<Record<string, string>>({});
  const [selectedStatus, setSelectedStatus] = useState(address.status);
  const [saving, setSaving] = useState(false);
  const [reparsing, setReparsing] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    // Initialize form fields from the address
    const init: Record<string, string> = {};
    for (const { key } of EDITABLE_FIELDS) {
      init[key] = (address[key as keyof Address] as string) || '';
    }
    setFields(init);
    setSelectedStatus(address.status);
  }, [address]);

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const updates: AddressUpdate = { status: selectedStatus };
      for (const { key } of EDITABLE_FIELDS) {
        const val = fields[key]?.trim();
        (updates as Record<string, string | null>)[key] = val || null;
      }
      const updated = await updateAddress(address.id, updates);
      onUpdated(updated);
      showToast('Address updated successfully', 'success');
    } catch (err) {
      showToast(`Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleReparse = async () => {
    if (reparsing) return;
    setReparsing(true);
    try {
      const updated = await reparseAddress(address.id);
      onUpdated(updated);
      showToast('Address re-parsed successfully', 'success');
    } catch (err) {
      showToast(`Re-parse failed: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    } finally {
      setReparsing(false);
    }
  };

  const confidencePercent = address.confidence !== null
    ? `${Math.round(address.confidence * 100)}%`
    : 'N/A';

  return (
    <div className="detail-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="detail-panel" id="address-detail-panel">
        {/* Header */}
        <div className="detail-panel-header">
          <div>
            <h2 style={{ marginBottom: 4 }}>Address #{address.id}</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
              <StatusBadge status={address.status as AddressStatus} />
              <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Confidence: {confidencePercent}
              </span>
            </div>
          </div>
          <button className="detail-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Raw Address */}
        <div>
          <div className="raw-address-block-label">Original Raw Address</div>
          <div className="raw-address-block">{address.raw_address}</div>
        </div>

        {/* Warnings */}
        {address.warnings.length > 0 && (
          <div className="warnings-section">
            <h3 style={{ marginBottom: 'var(--space-sm)', color: 'var(--color-review)' }}>
              ⚠ Warnings ({address.warnings.length})
            </h3>
            <ul className="warnings-list">
              {address.warnings.map((w, i) => (
                <li key={i} className="warning-item">
                  <span className="warning-icon">⚠</span>
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Editable Fields */}
        <h3 style={{ marginBottom: 'var(--space-md)' }}>Structured Fields</h3>
        <div className="fields-grid">
          {EDITABLE_FIELDS.map(({ key, label }) => (
            <div key={key} className="field-group">
              <label className="field-label" htmlFor={`field-${key}`}>{label}</label>
              <input
                id={`field-${key}`}
                className="field-input"
                type="text"
                value={fields[key] || ''}
                onChange={(e) => setFields((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder={`Enter ${label.toLowerCase()}`}
              />
            </div>
          ))}
        </div>

        {/* Status Selector */}
        <div className="field-group" style={{ marginBottom: 'var(--space-lg)', maxWidth: 300 }}>
          <label className="field-label" htmlFor="field-status">Status</label>
          <select
            id="field-status"
            className="field-input"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value as AddressStatus)}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Parse Log Info */}
        {address.parse_logs.length > 0 && (
          <div style={{ marginBottom: 'var(--space-lg)' }}>
            <h3 style={{ marginBottom: 'var(--space-sm)' }}>Parse History</h3>
            <div className="meta-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 'var(--space-sm)' }}>
              {address.parse_logs.map((log) => (
                <div key={log.id} className="meta-item" style={{ fontSize: '0.78rem', background: 'var(--bg-input)', padding: '6px 12px', borderRadius: 'var(--radius-sm)', width: '100%' }}>
                  <span>
                    {log.parsed_successfully ? '✅' : '❌'}
                    {' '}
                    <span className="meta-label">Model:</span> {log.model_used || 'N/A'}
                    {' · '}
                    <span className="meta-label">Prompt:</span> {log.prompt_version || 'N/A'}
                    {log.parsing_duration_ms !== null && (
                      <>{' · '}<span className="meta-label">Duration:</span> {log.parsing_duration_ms}ms</>
                    )}
                    {' · '}
                    <span className="meta-label">At:</span> {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="detail-actions">
          <button
            id="reparse-btn"
            className="btn"
            onClick={handleReparse}
            disabled={reparsing}
          >
            {reparsing ? <><span className="spinner" /> Re-parsing...</> : '🔄 Re-parse'}
          </button>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button
            id="save-btn"
            className="btn btn-success"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <><span className="spinner" /> Saving...</> : '💾 Save Changes'}
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
