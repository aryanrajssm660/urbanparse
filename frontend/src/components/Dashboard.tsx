import type { Stats } from '../types/address';

interface DashboardProps {
  stats: Stats;
  loading: boolean;
}

export default function Dashboard({ stats, loading }: DashboardProps) {
  if (loading) {
    return (
      <div className="stats-grid">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="stat-card">
            <div className="loading-shimmer" style={{ height: 44, marginBottom: 8 }} />
            <div className="loading-shimmer" style={{ height: 14, width: '60%', margin: '0 auto' }} />
          </div>
        ))}
      </div>
    );
  }

  const cards = [
    { key: 'total', label: 'Total Addresses', value: stats.total },
    { key: 'parsed', label: 'Parsed', value: stats.parsed },
    { key: 'review', label: 'Needs Review', value: stats.needs_review },
    { key: 'unparseable', label: 'Unparseable', value: stats.unparseable },
    { key: 'error', label: 'Errors', value: stats.error },
    { key: 'pending', label: 'Pending', value: stats.pending },
  ];

  return (
    <div className="stats-grid">
      {cards.map(({ key, label, value }) => (
        <div key={key} className={`stat-card ${key}`}>
          <div className="stat-value">{value}</div>
          <div className="stat-label">{label}</div>
        </div>
      ))}
    </div>
  );
}
