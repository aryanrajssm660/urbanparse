import type { Address, AddressStatus } from '../types/address';
import StatusBadge from './StatusBadge';

interface AddressListProps {
  addresses: Address[];
  loading: boolean;
  onSelect: (address: Address) => void;
  statusFilter: string | null;
  onFilterChange: (status: string | null) => void;
  page?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (page: number) => void;
}

const FILTERS: { label: string; value: string | null }[] = [
  { label: 'All', value: null },
  { label: 'Parsed', value: 'PARSED' },
  { label: 'Needs Review', value: 'NEEDS_REVIEW' },
  { label: 'Unparseable', value: 'UNPARSEABLE' },
  { label: 'Error', value: 'ERROR' },
  { label: 'Pending', value: 'PENDING' },
];

function getConfidenceColor(confidence: number | null): string {
  if (confidence === null) return 'var(--text-muted)';
  if (confidence >= 0.7) return 'var(--color-parsed)';
  if (confidence >= 0.4) return 'var(--color-review)';
  return 'var(--color-unparseable)';
}

function getConfidenceClass(confidence: number | null): string {
  if (confidence === null) return '';
  if (confidence >= 0.7) return 'confidence-high';
  if (confidence >= 0.4) return 'confidence-medium';
  return 'confidence-low';
}

export default function AddressList({
  addresses,
  loading,
  onSelect,
  statusFilter,
  onFilterChange,
  page = 1,
  pageSize = 50,
  total = addresses.length,
  onPageChange,
}: AddressListProps) {
  const totalPages = Math.ceil(total / pageSize) || 1;
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  return (
    <div>
      {/* Filter & Info Bar */}
      <div className="filter-bar" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 500 }}>
            Filter:
          </span>
          {FILTERS.map(({ label, value }) => (
            <button
              key={label}
              className={`filter-btn ${statusFilter === value ? 'active' : ''}`}
              onClick={() => {
                onFilterChange(value);
                if (onPageChange) onPageChange(1);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>
          Showing {startItem}–{endItem} of {total} addresses
        </div>
      </div>

      {/* Table */}
      <div className="table-container">
        {loading ? (
          <div style={{ padding: 'var(--space-xl)' }}>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="loading-shimmer" style={{ height: 48, marginBottom: 8 }} />
            ))}
          </div>
        ) : addresses.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <div className="empty-state-text">
              No addresses found{statusFilter ? ` for status filter "${statusFilter}"` : ''}. Add one above or seed the benchmark data.
            </div>
            {statusFilter && (
              <button
                className="btn btn-sm"
                style={{ marginTop: 'var(--space-sm)' }}
                onClick={() => onFilterChange(null)}
              >
                Clear Filter
              </button>
            )}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Raw Address</th>
                <th>City</th>
                <th>State</th>
                <th>PIN</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Warnings</th>
              </tr>
            </thead>
            <tbody>
              {addresses.map((addr) => (
                <tr key={addr.id} onClick={() => onSelect(addr)} id={`address-row-${addr.id}`}>
                  <td className="id-col">#{addr.id}</td>
                  <td className="raw-address" title={addr.raw_address}>{addr.raw_address}</td>
                  <td>{addr.city || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                  <td>{addr.state || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                    {addr.pin || <span style={{ color: 'var(--text-muted)' }}>—</span>}
                  </td>
                  <td>
                    <StatusBadge status={addr.status as AddressStatus} />
                  </td>
                  <td>
                    <div className="confidence-display">
                      <span className={`confidence-text ${getConfidenceClass(addr.confidence)}`}>
                        {addr.confidence !== null ? `${Math.round(addr.confidence * 100)}%` : '—'}
                      </span>
                      {addr.confidence !== null && (
                        <div className="confidence-bar">
                          <div
                            className="confidence-bar-fill"
                            style={{
                              width: `${Math.round(addr.confidence * 100)}%`,
                              background: getConfidenceColor(addr.confidence),
                            }}
                          />
                        </div>
                      )}
                    </div>
                  </td>
                  <td>
                    {addr.warnings && addr.warnings.length > 0 ? (
                      <span style={{ color: 'var(--color-review)', fontSize: '0.82rem' }}>
                        ⚠ {addr.warnings.length}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && onPageChange && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 'var(--space-md)', marginTop: 'var(--space-md)' }}>
          <button
            className="btn btn-sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || loading}
          >
            ← Previous
          </button>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Page {page} of {totalPages}
          </span>
          <button
            className="btn btn-sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || loading}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
