import { useState, useEffect, useCallback } from 'react';
import type { Address, Stats } from './types/address';
import { listAddresses, getStats, createAddress, seedAddresses, getAddress } from './api/client';
import Dashboard from './components/Dashboard';
import AddressForm from './components/AddressForm';
import AddressList from './components/AddressList';
import AddressDetail from './components/AddressDetail';

export default function App() {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 50;
  const [stats, setStats] = useState<Stats>({ total: 0, parsed: 0, needs_review: 0, unparseable: 0, error: 0, pending: 0 });
  const [selectedAddress, setSelectedAddress] = useState<Address | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [loadingAddresses, setLoadingAddresses] = useState(true);
  const [loadingStats, setLoadingStats] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const s = await getStats();
      setStats(s);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    } finally {
      setLoadingStats(false);
    }
  }, []);

  const fetchAddresses = useCallback(async () => {
    setLoadingAddresses(true);
    try {
      const resp = await listAddresses(page, pageSize, statusFilter || undefined);
      setAddresses(resp.items);
      setTotal(resp.total);
    } catch (err) {
      console.error('Failed to fetch addresses:', err);
    } finally {
      setLoadingAddresses(false);
    }
  }, [page, pageSize, statusFilter]);

  useEffect(() => {
    fetchStats();
    fetchAddresses();
  }, [fetchStats, fetchAddresses]);

  const handleCreateAddress = async (rawAddress: string) => {
    try {
      await createAddress(rawAddress);
      showToast('Address parsed successfully', 'success');
      await Promise.all([fetchAddresses(), fetchStats()]);
    } catch (err) {
      showToast(`Failed: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    }
  };

  const handleSeed = async () => {
    try {
      const result = await seedAddresses();
      showToast(result.message, 'success');
      setPage(1);
      await Promise.all([fetchAddresses(), fetchStats()]);
    } catch (err) {
      showToast(`Seed failed: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    }
  };

  const handleSelectAddress = async (addr: Address) => {
    // Fetch fresh detail with parse_logs
    try {
      const fresh = await getAddress(addr.id);
      setSelectedAddress(fresh);
    } catch {
      setSelectedAddress(addr);
    }
  };

  const handleAddressUpdated = (updated: Address) => {
    setSelectedAddress(updated);
    setAddresses((prev) =>
      prev.map((a) => (a.id === updated.id ? updated : a))
    );
    fetchStats();
    fetchAddresses();
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div>
          <h1>UrbanDash Address Parser</h1>
          <p className="app-header-subtitle">AI-powered Indian address parsing & review system</p>
        </div>
      </header>

      {/* Dashboard Stats */}
      <Dashboard stats={stats} loading={loadingStats} />

      {/* Address Input */}
      <AddressForm onSubmit={handleCreateAddress} onSeed={handleSeed} />

      {/* Address List */}
      <AddressList
        addresses={addresses}
        loading={loadingAddresses}
        onSelect={handleSelectAddress}
        statusFilter={statusFilter}
        onFilterChange={(newFilter) => {
          setStatusFilter(newFilter);
          setPage(1);
        }}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
      />

      {/* Detail Panel */}
      {selectedAddress && (
        <AddressDetail
          address={selectedAddress}
          onClose={() => setSelectedAddress(null)}
          onUpdated={handleAddressUpdated}
        />
      )}

      {/* Global Toast */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
