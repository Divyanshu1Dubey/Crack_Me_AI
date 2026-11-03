// /admin/import-center/batches/[id] — batch detail with live polling,
// materials table, audit log, publish / rollback / mock-test generation.

'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { importCenterAPI } from '@/lib/api';

type Batch = {
  id: number;
  status: string;
  source_label: string;
  total_files: number;
  files_processed: number;
  files_failed: number;
  questions_extracted: number;
  questions_found: number;
  questions_rejected: number;
  duplicates_skipped: number;
  theory_blocks_extracted: number;
  images_extracted: number;
  ai_enrichment_queued: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  summary: Record<string, unknown> & { publish?: PublishState; rebuild?: PublishState };
  error_report: Array<Record<string, unknown>>;
  materials_count: number;
  needs_review_count: number;
  is_stale?: boolean;
  recent_audit_logs?: Array<{
    id: number;
    level: string;
    code: string;
    message: string;
    created_at: string;
  }>;
};

// Background publish progress, stored by the API in batch.summary.publish;
// a running test rebuild (Republish Tests) is batch.summary.rebuild
// (kind 'republish'; older API versions wrote it into summary.publish).
type PublishState = {
  state: 'running' | 'done' | 'failed';
  kind?: 'republish';
  started_at?: string;
  finished_at?: string;
  heartbeat_at?: string;
  published?: number;
  tests_built?: number;
  rows_done?: number;
  error?: string;
};

// Same rules as the API: a background publish that has not reported for 30
// minutes has died with its process; a rebuild runs inside its request, so
// one older than 5 minutes died with it.
const PUBLISH_STALE_MS = 30 * 60 * 1000;
const REBUILD_STALE_MS = 5 * 60 * 1000;

function isLive(state?: PublishState): boolean {
  if (state?.state !== 'running') return false;
  const lastBeat = state.heartbeat_at || state.started_at;
  if (!lastBeat) return true;
  const limit = state.kind === 'republish' ? REBUILD_STALE_MS : PUBLISH_STALE_MS;
  return Date.now() - new Date(lastBeat).getTime() <= limit;
}

type Material = {
  id: number;
  original_filename: string;
  file_format: string;
  file_size_bytes: number;
  detected_type: string;
  parse_status: string;
  question_count: number;
  questions_found: number;
  questions_rejected: number;
  theory_block_count: number;
  image_count: number;
  duplicate_count: number;
  parser_used: string;
  duration_ms: number;
  parse_warnings: string[];
  parse_errors: string[];
  parsed_at: string | null;
};

const STATUS_COLORS: Record<string, string> = {
  queued: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-300',
  processing: 'bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300',
  completed: 'bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300',
  partial: 'bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300',
  failed: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-500/20 dark:text-gray-300',
  // material parse_status values
  parsed: 'bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300',
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-300',
  skipped: 'bg-gray-100 text-gray-800 dark:bg-gray-500/20 dark:text-gray-300',
};

// Alert boxes, light + dark.
const ALERT = {
  error: 'border-red-300 bg-red-50 text-red-800 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300',
  warn: 'border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-500/40 dark:bg-orange-500/10 dark:text-orange-300',
  info: 'border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-500/40 dark:bg-blue-500/10 dark:text-blue-300',
  ok: 'border-green-300 bg-green-50 text-green-800 dark:border-green-500/40 dark:bg-green-500/10 dark:text-green-300',
};

export default function BatchDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [auditPage, setAuditPage] = useState(1);
  const [audit, setAudit] = useState<{ items: any[]; total: number; page_size: number; page: number }>({ items: [], total: 0, page_size: 50, page: 1 });
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [mockModal, setMockModal] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = async (showLoading = false) => {
    try {
      const [b, m] = await Promise.all([
        importCenterAPI.getBatch(id),
        importCenterAPI.getBatchMaterials(id),
      ]);
      setBatch(b.data);
      setMaterials(m.data);
    } catch (e: any) {
      setActionError(e?.response?.data?.error || e?.message || 'Failed to load');
    }
  };

  useEffect(() => {
    if (!id) return;
    load();
    pollRef.current = setInterval(() => {
      // Only poll while parsing or while a publish / test rebuild runs.
      setBatch((prev) => {
        if (
          !prev ||
          prev.status === 'processing' ||
          prev.status === 'queued' ||
          prev.summary?.publish?.state === 'running' ||
          prev.summary?.rebuild?.state === 'running'
        ) {
          load();
        }
        return prev;
      });
    }, 4000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const run = async () => {
      try {
        const r = await importCenterAPI.getBatchAudit(id, auditPage, 50);
        setAudit(r.data);
      } catch {
        /* ignore */
      }
    };
    run();
  }, [id, auditPage, batch?.status]);

  const doAction = async (action: 'cancel' | 'publish' | 'rollback' | 'republish', opts?: any) => {
    setActionPending(action);
    setActionError(null);
    try {
      if (action === 'cancel') await importCenterAPI.cancelBatch(id);
      if (action === 'publish') await importCenterAPI.publishBatch(id, opts || { only_publish: false, build_tests: true, max_per_test: 100 });
      if (action === 'rollback') await importCenterAPI.rollbackBatch(id, opts?.delete_published || false);
      if (action === 'republish') await importCenterAPI.republishBatch(id);
      await load();
    } catch (e: any) {
      setActionError(e?.response?.data?.error || e?.message || `Failed to ${action}`);
    } finally {
      setActionPending(null);
    }
  };

  if (!batch) {
    return <div className="text-muted-foreground">Loading batch #{id}…</div>;
  }

  const live = batch.status === 'processing' || batch.status === 'queued';
  const rawPublish = batch.summary?.publish;
  // An in-slot rebuild state (older API) is shown as a rebuild, not a publish.
  const legacyRebuild = rawPublish?.kind === 'republish' ? rawPublish : undefined;
  const publishState = legacyRebuild ? undefined : rawPublish;
  const rebuilding = isLive(batch.summary?.rebuild) || isLive(legacyRebuild);
  const publishStale = publishState?.state === 'running' && !isLive(publishState);
  const publishing = isLive(publishState);
  const busy = publishing || rebuilding;
  // A cancelled batch can still publish what it staged before the cancel;
  // a rolled-back one has nothing left (the API answers 409 for both cases
  // when there is nothing to publish).
  const rolledBack = Boolean(batch.summary?.rollback);
  const canPublish =
    batch.status === 'completed' ||
    batch.status === 'partial' ||
    (batch.status === 'cancelled' && !rolledBack && batch.materials_count > 0);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Batch #{batch.id}</h2>
          <p className="text-sm text-muted-foreground">{batch.source_label}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded px-3 py-1 text-xs font-medium ${STATUS_COLORS[batch.status]}`}>{batch.status}</span>
          <button
            type="button"
            disabled={!live || actionPending === 'cancel'}
            onClick={() => doAction('cancel')}
            title={live ? 'Stop parsing after the current file' : 'Only a queued or processing batch can be cancelled'}
            className="rounded border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50"
          >
            {actionPending === 'cancel' ? 'Cancelling…' : 'Cancel'}
          </button>
          <button
            type="button"
            disabled={!canPublish || busy || actionPending === 'publish'}
            onClick={() => doAction('publish')}
            className="rounded bg-primary px-3 py-1 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {actionPending === 'publish' || publishing ? 'Publishing…' : 'Publish & Build Tests'}
          </button>
          <button
            type="button"
            disabled={live || busy || actionPending === 'republish'}
            onClick={() => doAction('republish')}
            className="rounded border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50"
          >
            {actionPending === 'republish' || rebuilding ? 'Rebuilding tests…' : 'Republish Tests'}
          </button>
          <button
            type="button"
            disabled={live || busy || actionPending === 'rollback'}
            onClick={() => {
              if (confirm('Rollback will delete ALL materials, staging rows, and auto-generated tests for this batch. Continue?')) {
                doAction('rollback', { delete_published: false });
              }
            }}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-500/40 dark:text-red-400 dark:hover:bg-red-500/10"
          >
            {actionPending === 'rollback' ? 'Rolling back…' : 'Rollback'}
          </button>
        </div>
      </header>

      {actionError && (
        <div className={`rounded border p-3 text-sm ${ALERT.error}`}>{actionError}</div>
      )}

      {live && batch.is_stale && (
        <div className={`rounded border p-3 text-sm ${ALERT.warn}`}>
          No progress for over 30 minutes — the background parse has probably stopped (for example after a
          server restart). Cancel this batch and upload the files again.
        </div>
      )}

      {rebuilding && actionPending !== 'republish' && (
        <div className={`rounded border p-3 text-sm ${ALERT.info}`} role="status">
          Rebuilding this batch&apos;s tests… Publish and rollback are available again once it finishes.
        </div>
      )}

      {publishState && (
        <div
          className={`rounded border p-3 text-sm ${
            publishState.state === 'failed' || publishStale ? ALERT.error : publishing ? ALERT.info : ALERT.ok
          }`}
        >
          {publishing && (
            <>
              Publishing in the background
              {publishState.rows_done ? ` (${publishState.rows_done} rows processed)` : ''}… this page updates
              automatically.
            </>
          )}
          {publishStale && (
            <>
              The last publish stopped reporting progress (probably a server restart). Publishing is safe to
              repeat — already-published questions are skipped — so you can start it again.
            </>
          )}
          {publishState.state === 'done' && (
            <>
              Last publish: {publishState.published ?? 0} question(s) published, {publishState.tests_built ?? 0}{' '}
              test(s) built
              {publishState.finished_at ? ` (${new Date(publishState.finished_at).toLocaleString()})` : ''}.
            </>
          )}
          {publishState.state === 'failed' && <>Last publish failed: {publishState.error || 'unknown error'}</>}
        </div>
      )}

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">
        <Stat label="Files" value={`${batch.files_processed}/${batch.total_files}`} />
        <Stat label="Found" value={batch.questions_found} />
        <Stat label="Imported" value={batch.questions_extracted} accent="text-green-600" />
        <Stat label="Rejected" value={batch.questions_rejected} accent="text-orange-600" />
        <Stat label="Duplicates" value={batch.duplicates_skipped} accent="text-purple-600" />
        <Stat label="Images" value={batch.images_extracted} />
        <Stat label="Theory" value={batch.theory_blocks_extracted} />
        <Stat label="Needs Review" value={batch.needs_review_count} accent="text-rose-600" />
      </section>

      <section className="rounded border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-semibold">Generate Mock Test</h3>
          <button
            type="button"
            onClick={() => setMockModal(true)}
            disabled={live}
            className="rounded bg-primary px-3 py-1 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            + New Mock
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          Build a single auto-test from this batch using one of the strategies below.
        </p>
      </section>

      <section className="rounded border border-border bg-card p-4">
        <h3 className="mb-3 font-semibold">Materials ({materials.length})</h3>
        {materials.length === 0 ? (
          <div className="text-sm text-muted-foreground">No materials recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm [&_td]:px-3 [&_th]:px-3">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-2">Filename</th>
                  <th className="py-2">Format</th>
                  <th className="py-2">Detected</th>
                  <th className="py-2">Parser</th>
                  <th className="py-2 text-right">Found</th>
                  <th className="py-2 text-right">Saved</th>
                  <th className="py-2 text-right">Dupes</th>
                  <th className="py-2 text-right">Images</th>
                  <th className="py-2 text-right">Ms</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {materials.map((m) => (
                  <tr key={m.id} className="border-b last:border-0">
                    <td className="py-2 max-w-xs truncate" title={m.original_filename}>{m.original_filename}</td>
                    <td className="py-2 text-xs uppercase">{m.file_format}</td>
                    <td className="py-2 text-xs">{m.detected_type}</td>
                    <td className="py-2 text-xs">{m.parser_used || '—'}</td>
                    <td className="py-2 text-right">{m.questions_found}</td>
                    <td className="py-2 text-right">{m.question_count}</td>
                    <td className="py-2 text-right">{m.duplicate_count}</td>
                    <td className="py-2 text-right">{m.image_count}</td>
                    <td className="py-2 text-right text-xs">{m.duration_ms}</td>
                    <td className="py-2">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[m.parse_status] || ''}`}>
                        {m.parse_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-semibold">Audit Log ({audit.total})</h3>
          <div className="flex items-center gap-2 text-xs">
            <button
              type="button"
              disabled={auditPage <= 1}
              onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
              className="rounded border border-border px-2 py-1 disabled:opacity-50"
            >
              ‹ Prev
            </button>
            <span>
              {audit.page} / {Math.max(1, Math.ceil(audit.total / audit.page_size))}
            </span>
            <button
              type="button"
              disabled={audit.page * audit.page_size >= audit.total}
              onClick={() => setAuditPage((p) => p + 1)}
              className="rounded border border-border px-2 py-1 disabled:opacity-50"
            >
              Next ›
            </button>
          </div>
        </div>
        {audit.items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No audit entries yet.</div>
        ) : (
          <ul className="space-y-1 text-xs">
            {audit.items.map((l) => (
              <li key={l.id} className="flex gap-2 rounded border border-border bg-background px-3 py-1.5">
                <span className="text-muted-foreground">{new Date(l.created_at).toLocaleTimeString()}</span>
                <span className={`uppercase font-medium ${
                  l.level === 'error' ? 'text-red-600' :
                  l.level === 'warning' ? 'text-orange-600' : 'text-blue-600'
                }`}>{l.level}</span>
                <span className="text-muted-foreground">[{l.code}]</span>
                <span className="flex-1 truncate">{l.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {batch.error_report && batch.error_report.length > 0 && (
        <section className={`rounded border p-4 ${ALERT.error}`}>
          <h3 className="mb-2 font-semibold">Errors ({batch.error_report.length})</h3>
          <ul className="space-y-1 text-xs">
            {batch.error_report.slice(0, 20).map((e: any, i: number) => (
              <li key={i}>
                <code>{e.file}</code>: {e.error}
              </li>
            ))}
          </ul>
        </section>
      )}

      {mockModal && (
        <MockModal
          batchId={batch.id}
          onClose={() => setMockModal(false)}
          onSuccess={() => {
            setMockModal(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded border border-border bg-card p-3">
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className={`mt-0.5 text-lg font-bold ${accent || ''}`}>{value}</div>
    </div>
  );
}

function MockModal({ batchId, onClose, onSuccess }: { batchId: number; onClose: () => void; onSuccess: () => void }) {
  const [strategy, setStrategy] = useState('by_subject');
  const [count, setCount] = useState(50);
  const [difficulty, setDifficulty] = useState('mixed');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<{ test_id: number; test_title: string; question_count: number } | null>(null);

  const submit = async () => {
    setSubmitting(true);
    setErr(null);
    try {
      const r = await importCenterAPI.generateMock(batchId, {
        strategy, question_count: count, difficulty,
      });
      setResult(r.data);
    } catch (e: any) {
      setErr(e?.response?.data?.error || e?.message || 'Failed to generate mock');
    } finally {
      setSubmitting(false);
    }
  };

  // Portal to <body>: the fixed overlay stays relative to the viewport
  // whatever the app shell's wrappers do (a transform, filter or layout
  // containment on an ancestor would make it the containing block).
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded border border-border bg-card p-6">
        <h3 className="mb-4 text-lg font-semibold">Generate Mock Test</h3>
        {result ? (
          <div className="space-y-3">
            <div className={`rounded border p-3 text-sm ${ALERT.ok}`}>
              Created <strong>{result.test_title}</strong> with {result.question_count} questions.
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={onSuccess} className="rounded bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground">
                Done
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs text-muted-foreground">Strategy</span>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className="mt-1 block w-full rounded border border-border bg-background px-3 py-1.5 text-sm">
                <option value="entire_file">Entire File</option>
                <option value="by_subject">By Subject</option>
                <option value="by_chapter">By Chapter</option>
                <option value="by_topic">By Topic</option>
                <option value="by_difficulty">By Difficulty</option>
                <option value="random">Random Mix</option>
                <option value="image_based">Image Based</option>
                <option value="grand">Grand Test</option>
                <option value="revision">Revision Test</option>
                <option value="weekly">Weekly Test</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Question count (1-2000)</span>
              <input
                type="number"
                min={1}
                max={2000}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="mt-1 block w-full rounded border border-border bg-background px-3 py-1.5 text-sm"
              />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Difficulty</span>
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="mt-1 block w-full rounded border border-border bg-background px-3 py-1.5 text-sm">
                <option value="mixed">Mixed</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </label>
            {err && <div className={`rounded border p-2 text-sm ${ALERT.error}`}>{err}</div>}
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={onClose} className="rounded border border-border px-4 py-1.5 text-sm">
                Cancel
              </button>
              <button type="button" onClick={submit} disabled={submitting} className="rounded bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50">
                {submitting ? 'Generating…' : 'Generate'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}