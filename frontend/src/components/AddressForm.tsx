import { useState } from 'react';

interface AddressFormProps {
  onSubmit: (rawAddress: string) => Promise<void>;
  onSeed: () => Promise<void>;
}

export default function AddressForm({ onSubmit, onSeed }: AddressFormProps) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    setLoading(true);
    try {
      await onSubmit(input.trim());
      setInput('');
    } finally {
      setLoading(false);
    }
  };

  const handleSeed = async () => {
    if (seeding) return;
    setSeeding(true);
    try {
      await onSeed();
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div style={{ marginBottom: 'var(--space-lg)' }}>
      <form className="add-form" onSubmit={handleSubmit}>
        <input
          id="address-input"
          className="add-form-input"
          type="text"
          placeholder="Enter a raw delivery address to parse..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={1000}
          disabled={loading}
        />
        <button
          id="submit-address"
          type="submit"
          className="btn btn-primary"
          disabled={loading || !input.trim()}
        >
          {loading ? (
            <>
              <span className="spinner" />
              Parsing...
            </>
          ) : (
            '⚡ Parse Address'
          )}
        </button>
        <button
          id="seed-benchmark"
          type="button"
          className="btn btn-warning"
          onClick={handleSeed}
          disabled={seeding}
        >
          {seeding ? (
            <>
              <span className="spinner" />
              Seeding...
            </>
          ) : (
            '📋 Seed 15 Benchmark'
          )}
        </button>
      </form>
    </div>
  );
}
