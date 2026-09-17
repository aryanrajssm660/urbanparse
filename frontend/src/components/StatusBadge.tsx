import type { AddressStatus } from '../types/address';

interface StatusBadgeProps {
  status?: AddressStatus | string | null;
}

const STATUS_LABELS: Record<string, string> = {
  PARSED: 'Parsed',
  NEEDS_REVIEW: 'Needs Review',
  UNPARSEABLE: 'Unparseable',
  ERROR: 'Error',
  PENDING: 'Pending',
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  if (!status) {
    return <span className="badge badge-pending">Pending</span>;
  }
  const label = STATUS_LABELS[status] || status;
  const className = `badge badge-${status.toLowerCase()}`;
  return <span className={className}>{label}</span>;
}
