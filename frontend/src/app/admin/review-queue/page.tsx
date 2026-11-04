'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ClipboardCheck, Loader2, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { keyAuditAPI } from '@/lib/api';
import {
  STATUS_HINTS,
  STATUS_LABELS,
  STATUS_ORDER,
  type AuditStatus,
  type QueueRow,
  batchEligible,
  batchItems,
  describeError,
  signalLabel,
  statusTone,
} from '@/lib/keyAudit';
import AuditDetailPanel, { type ResolvedResult } from './AuditDetailPanel';

interface Summary {
  total: number;
  stale: number;
  status: Record<string, number>;
  reasons: Record<string, number>;
  open_signals: Record<string, number>;
  suggested_from: Record<string, number>;
  claimed: number;
}

const EXAMS = [
  { value: '', label: 'All exams' },
  { value: 'cms', label: 'UPSC CMS' },
  { value: 'neet_pg', label: 'NEET PG' },
  { value: 'ini_cet', label: 'INI-CET' },
];
const PAGE_SIZE = 25;
const BATCH_REASON = 'Printed answer key compared with the question on the source page.';

export default function ReviewQueuePage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const isAdmin = !!user && (user.role === 'admin' || !!user.is_admin);
  const me = user?.username ?? null;

  const [summary, setSummary] = useState<Summary | null>(null);
  const [rows, setRows] = useState<QueueRow[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [status, setStatus] = useState<AuditStatus | ''>('needs_review');
  const [exam, setExam] = useState('');
  const [reason, setReason] = useState('');
  const [printedOnly, setPrintedOnly] = useState(false);
  const [unclaimed, setUnclaimed] = useState(true);
  const [search, setSearch] = useState('');

  const [selected, setSelected] = useState<number | null>(null);
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const [batchReason, setBatchReason] = useState(BATCH_REASON);
  const [batchConfirmed, setBatchConfirmed] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchMessage, setBatchMessage] = useState<string | null>(null);
  const [lastResolved, setLastResolved] = useState<string | null>(null);

  const params = useMemo(() => {
    const p: Record<string, string | number> = { page, page_size: PAGE_SIZE };
    if (status) p.status = status;
    if (exam) p.exam = exam;
    if (reason) p.reason = reason;
    if (printedOnly) p.suggested_from = 'source_key_mismatch';
    if (unclaimed) p.unclaimed = 'true';
    if (search.trim() && /^\d+$/.test(search.trim())) p.q = search.trim();
    return p;
  }, [page, status, exam, reason, printedOnly, unclaimed, search]);

  const loadSummary = useCallback(async () => {
    try {
      const res = await keyAuditAPI.summary(exam ? { exam } : undefined);
      setSummary(res.data as Summary);
    } catch {
      /* the list shows the error */
    }
  }, [exam]);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await keyAuditAPI.list(params);
      setRows((res.data?.results ?? []) as QueueRow[]);
      setCount(Number(res.data?.count ?? 0));
    } catch (err) {
      setError(describeError(err));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [params]);

  // `?q=<question id>` (the editor's provenance panel links here): show that question in any status.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const q = new URLSearchParams(window.location.search).get('q');
    if (q && /^\d+$/.test(q)) {
      setSearch(q);
      setStatus('');
      setUnclaimed(false);
      setSelected(Number(q));
    }
  }, []);

  // On a phone the detail sits below the filters: bring it into view when a question is opened.
  const detailRef = React.useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (selected === null || typeof window === 'undefined') return;
    if (window.matchMedia?.('(max-width: 1023px)').matches) {
      detailRef.current?.scrollIntoView({ block: 'start' });
    }
  }, [selected]);

  useEffect(() => { if (isAdmin) loadSummary(); }, [isAdmin, loadSummary]);
  useEffect(() => { if (isAdmin) loadList(); }, [isAdmin, loadList]);
  useEffect(() => { setPage(1); setTicked(new Set()); }, [status, exam, reason, printedOnly, unclaimed, search]);

  const reasons = useMemo(() => {
    if (!summary) return [];
    return Object.entries(summary.reasons)
      .filter(([key]) => !status || key.startsWith(`${status}/`))
      .map(([key, n]) => ({ value: key.split('/')[1], n }));
  }, [summary, status]);

  function onResolved(result: ResolvedResult) {
    setLastResolved(`Q${result.question_id}: key ${result.current_key || '–'}, now ${STATUS_LABELS[result.audit_status as AuditStatus] ?? result.audit_status}.`);
    const index = rows.findIndex((r) => r.question_id === result.question_id);
    const next = rows[index + 1] ?? null;
    setSelected(next ? next.question_id : null);
    loadList();
    loadSummary();
  }

  function toggle(qid: number) {
    setTicked((prev) => {
      const next = new Set(prev);
      if (next.has(qid)) next.delete(qid); else if (next.size < PAGE_SIZE) next.add(qid);
      return next;
    });
  }

  async function acceptPrinted() {
    const items = batchItems(rows, ticked, me);
    if (!items.length) return;
    setBatchBusy(true);
    setBatchMessage(null);
    try {
      const res = await keyAuditAPI.acceptSourceKeys(batchReason.trim(), items);
      const results = (res.data?.results ?? []) as { question_id: number; ok: boolean; error?: string }[];
      const failed = results.filter((r) => !r.ok);
      setBatchMessage(`${res.data?.accepted ?? 0} key(s) changed to the printed key.`
        + (failed.length ? ` Not changed: ${failed.map((r) => `Q${r.question_id} (${r.error})`).join(', ')}.` : ''));
      setTicked(new Set());
      setBatchConfirmed(false);
      loadList();
      loadSummary();
    } catch (err) {
      setBatchMessage(describeError(err));
    } finally {
      setBatchBusy(false);
    }
  }

  if (authLoading) {
    return <p className="p-6 [.page-container_&]:px-0 text-muted-foreground">Checking access…</p>;
  }
  if (!isAuthenticated || !isAdmin) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 [.page-container_&]:px-0 text-center text-foreground">
        <p className="mb-3 text-muted-foreground">You need admin access to view this page.</p>
        <Button onClick={() => router.push('/login?next=' + encodeURIComponent('/admin/review-queue'))}>Sign in</Button>
      </div>
    );
  }

  const eligible = rows.filter((r) => batchEligible(r, me));
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 [.page-container_&]:p-0 text-foreground">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
          <h1 className="text-xl font-semibold">Answer-key review</h1>
          {summary && <span className="text-xs text-muted-foreground">{summary.total} audited · {summary.claimed} claimed</span>}
        </div>
        <Button variant="outline" size="sm" onClick={() => { loadList(); loadSummary(); }} aria-label="Refresh">
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        Nothing here changes a key until you record a decision. AI reviews are review signals, not evidence; a printed
        source key is the document the question was copied from. A decision is &ldquo;verified&rdquo; only with strong evidence.
      </p>

      <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label="Status">
        {(['', ...STATUS_ORDER] as (AuditStatus | '')[]).map((value) => {
          const n = value ? summary?.status?.[value] ?? 0 : summary?.total ?? 0;
          const active = status === value;
          return (
            <button key={value || 'all'} role="tab" aria-selected={active} onClick={() => { setStatus(value); setReason(''); }}
              title={value ? STATUS_HINTS[value] : 'Every audited question'}
              className={`rounded-full border px-3 py-1 text-xs ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-accent'}`}>
              {value ? STATUS_LABELS[value] : 'All'} <span className="opacity-75">{n}</span>
            </button>
          );
        })}
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-2 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Exam</span>
          <select value={exam} onChange={(e) => setExam(e.target.value)} className="rounded-md border border-border bg-background px-2 py-1.5">
            {EXAMS.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Main reason</span>
          <select value={reason} onChange={(e) => setReason(e.target.value)} className="max-w-xs rounded-md border border-border bg-background px-2 py-1.5">
            <option value="">Any</option>
            {reasons.map((r) => <option key={r.value} value={r.value}>{signalLabel(r.value)} ({r.n})</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Question id</span>
          <input value={search} onChange={(e) => setSearch(e.target.value)} inputMode="numeric" placeholder="e.g. 10290"
            className="w-28 rounded-md border border-border bg-background px-2 py-1.5" />
        </label>
        <label className="flex items-center gap-1.5 pb-1.5">
          <input type="checkbox" checked={printedOnly} onChange={(e) => setPrintedOnly(e.target.checked)} />
          <span>Printed key differs ({summary?.suggested_from?.source_key_mismatch ?? 0})</span>
        </label>
        <label className="flex items-center gap-1.5 pb-1.5">
          <input type="checkbox" checked={unclaimed} onChange={(e) => setUnclaimed(e.target.checked)} />
          <span>Hide claimed by others</span>
        </label>
      </div>

      {lastResolved && <p className="mb-3 rounded-md bg-emerald-100 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-500/15 dark:text-emerald-300" role="status">{lastResolved}</p>}
      {error && <p className="mb-3 text-sm text-destructive" role="alert">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section aria-label="Queue" className={selected ? 'hidden lg:block' : ''}>
          {loading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</p>}
          {!loading && rows.length === 0 && <p className="text-sm text-muted-foreground">Nothing in this view.</p>}
          <ul className="space-y-2">
            {rows.map((row) => {
              const canTick = printedOnly && batchEligible(row, me);
              return (
                <li key={row.question_id}
                  className={`rounded-lg border p-2.5 ${selected === row.question_id ? 'border-primary bg-primary/5' : 'border-border'}`}>
                  <div className="flex items-start gap-2">
                    {printedOnly && (
                      <input type="checkbox" className="mt-1" disabled={!canTick} checked={ticked.has(row.question_id)}
                        onChange={() => toggle(row.question_id)} aria-label={`Select question ${row.question_id} for the printed key`} />
                    )}
                    <button type="button" onClick={() => setSelected(row.question_id)} className="min-w-0 flex-1 text-left">
                      <div className="flex flex-wrap items-center gap-1.5 text-xs">
                        <span className="font-semibold">Q{row.question_id}</span>
                        <span className="text-muted-foreground">{row.exam_type} {row.year || ''} · {row.subject}</span>
                        <Badge variant={statusTone(row.status)}>{STATUS_LABELS[row.status] ?? row.status}</Badge>
                        <span className="text-muted-foreground">priority {Math.round(row.priority)}</span>
                        {row.claimed_by && <span className="text-amber-700 dark:text-amber-400">claimed by {row.claimed_by}</span>}
                      </div>
                      <p className="mt-1 line-clamp-2 text-sm">{row.question_text}</p>
                      <p className="mt-1 text-xs">
                        key <strong>{row.stored_key || '–'}</strong>
                        {row.suggested_key && <> → suggested <strong>{row.suggested_key}</strong> <span className="text-muted-foreground">({signalLabel(row.suggested_from)})</span></>}
                        {row.printed_key && <span className="text-muted-foreground"> · {row.printed_key.source_file}, PDF p. {row.printed_key.question_page}, Q{row.printed_key.question_number}</span>}
                      </p>
                      {row.open_signals.length > 0 && (
                        <p className="mt-1 text-xs text-muted-foreground">{row.open_signals.map(signalLabel).join(' · ')}</p>
                      )}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
          {pages > 1 && (
            <div className="mt-3 flex items-center justify-between text-sm">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <span className="text-muted-foreground">Page {page} of {pages} · {count} question(s)</span>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          )}

          {printedOnly && eligible.length > 0 && (
            <div className="mt-4 space-y-2 rounded-lg border border-amber-500/60 p-3">
              <p className="text-sm font-semibold">Accept the printed key for the ticked questions</p>
              <p className="text-xs text-muted-foreground">
                Each ticked question becomes its own key change (old key, you, this reason, the printed key as evidence).
                Printed keys are tier 4, so the result is &ldquo;likely correct&rdquo;. Tick only questions you compared with the source page.
              </p>
              <div className="flex flex-wrap gap-2 text-xs">
                <Button variant="outline" size="sm" onClick={() => setTicked(new Set(eligible.map((r) => r.question_id)))}>Tick all {eligible.length} on this page</Button>
                <Button variant="outline" size="sm" onClick={() => setTicked(new Set())}>Clear</Button>
              </div>
              <textarea value={batchReason} onChange={(e) => setBatchReason(e.target.value)} rows={2} aria-label="Reason for the batch"
                className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm" />
              <label className="flex items-start gap-1.5 text-sm">
                <input type="checkbox" className="mt-0.5" checked={batchConfirmed} onChange={(e) => setBatchConfirmed(e.target.checked)} />
                <span>I compared each ticked question with its printed answer.</span>
              </label>
              <Button variant="warning" disabled={!ticked.size || !batchConfirmed || batchBusy || batchReason.trim().length < 10} onClick={acceptPrinted}>
                {batchBusy && <Loader2 className="h-4 w-4 animate-spin" />} Change {ticked.size} key(s) to the printed key
              </Button>
              {batchMessage && <p className="text-sm" role="status">{batchMessage}</p>}
            </div>
          )}
        </section>

        {/* min-h-screen on phones: the page must be tall enough to scroll the detail up while it loads */}
        <section ref={detailRef} aria-label="Selected question"
          className={`scroll-mt-20 lg:scroll-mt-4 ${selected ? 'min-h-screen lg:min-h-0' : 'hidden lg:block'}`}>
          {selected ? (
            <div className="lg:sticky lg:top-4">
              <button type="button" onClick={() => setSelected(null)} className="mb-2 text-sm text-primary lg:hidden">← Back to the list</button>
              <AuditDetailPanel key={selected} questionId={selected} onResolved={onResolved} onClose={() => setSelected(null)} />
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">Select a question to review it.</p>
          )}
        </section>
      </div>
    </div>
  );
}
