// /admin/import-center/search — full-text search across the extracted staging area.

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { importCenterAPI } from '@/lib/api';

type Result = {
  id: number;
  material: number;
  material_filename: string;
  question_text: string;
  correct_answer: string;
  inferred_subject: string;
  inferred_topic: string;
  status: string;
};

export default function SearchPage() {
  const [term, setTerm] = useState('');
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState(0);

  const run = async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setCount(0);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await importCenterAPI.search(q);
      setResults(r.data.items || []);
      setCount(r.data.count || 0);
    } catch (e: any) {
      setError(e?.response?.data?.error || e?.message || 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  // Debounce
  useEffect(() => {
    const t = setTimeout(() => run(term), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term]);

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-xl font-bold">Search</h2>
        <p className="text-sm text-muted-foreground">Search by question text, option, explanation, topic, or filename.</p>
      </header>

      <input
        type="text"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        placeholder="Search the staging area…"
        className="block w-full rounded border border-border bg-background px-4 py-2 text-sm"
        autoFocus
      />

      {error && <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}

      {loading ? (
        <div className="text-sm text-muted-foreground">Searching…</div>
      ) : term && results.length === 0 ? (
        <div className="text-sm text-muted-foreground">No matches.</div>
      ) : (
        <section className="rounded border border-border bg-card p-4">
          <div className="mb-3 text-xs text-muted-foreground">{count} match(es)</div>
          <ul className="space-y-2">
            {results.map((r) => (
              <li key={r.id} className="rounded border border-border bg-background p-3 text-sm">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    Batch <Link href={`/admin/import-center/batches/${r.material}`} className="hover:underline">#{r.material}</Link>
                    {' · '}
                    {r.inferred_subject || '—'}
                    {' → '}
                    {r.inferred_topic || '—'}
                  </span>
                  <span>Answer: <strong>{r.correct_answer || '?'}</strong></span>
                </div>
                <p className="mt-1 line-clamp-3">{r.question_text}</p>
                <div className="mt-1 truncate text-xs text-muted-foreground" title={r.material_filename}>{r.material_filename}</div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}