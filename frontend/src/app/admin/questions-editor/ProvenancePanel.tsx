'use client';

import { useCallback, useEffect, useId, useState } from 'react';
import Link from 'next/link';
import { History, Loader2, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  editorialAPI,
  type KeyChangeRecord,
  type Provenance,
  type VerifyResult,
} from '@/lib/editorialAPI';
import { STATUS_HINTS, signalLabel, statusTone, type AuditStatus } from '@/lib/keyAudit';
import {
  EXPLANATION_STATUS_HINTS,
  EXPLANATION_STATUS_LABELS,
  auditStatusLabel,
  canMarkReviewed,
  describeEditorialError,
  evidenceSummary,
  explanationTone,
  formatWhen,
  keyChangeLine,
  originLabel,
  reviewQueueLink,
} from './editorialRules';

export interface ProvenanceState {
  data: Provenance | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** GET /api/questions/<id>/provenance/ (reloaded with `reload()` after every editor decision). */
export function useProvenance(questionId: number): ProvenanceState {
  const [data, setData] = useState<Provenance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    editorialAPI.provenance(questionId)
      .then((res) => { if (alive) setData(res.data); })
      .catch((err) => { if (alive) setError(describeEditorialError(err)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [questionId, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, loading, error, reload };
}

const rowClass = 'flex flex-wrap items-center gap-x-2 gap-y-1 text-sm';

/**
 * Where the question's key and explanation stand: the stored key and its answer-key audit (with the
 * way to the review queue), the editor's key confirmation, the explanation's status, origin, the key it
 * was written for and who reviewed it, and the immutable key history.
 */
export default function ProvenancePanel({
  questionId,
  state,
  onVerified,
  onReviewed,
}: {
  questionId: number;
  state: ProvenanceState;
  onVerified: (result: VerifyResult) => void;
  onReviewed: (updatedAt: string) => void;
}) {
  const ids = useId();
  const { data, loading, error, reload } = state;
  const [history, setHistory] = useState<KeyChangeRecord[] | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'' | 'verify' | 'unverify' | 'review'>('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [unverifyReason, setUnverifyReason] = useState('');
  const [askReason, setAskReason] = useState(false);

  const keyChangeCount = data?.key_change_count ?? 0;
  useEffect(() => {
    let alive = true;
    setHistoryError(null);
    editorialAPI.keyHistory(questionId)
      .then((res) => { if (alive) setHistory(res.data.changes ?? []); })
      .catch((err) => { if (alive) setHistoryError(describeEditorialError(err)); });
    return () => { alive = false; };
  }, [questionId, keyChangeCount]);

  async function verify(action: 'verify' | 'unverify') {
    setBusy(action);
    setActionError(null);
    try {
      const res = await editorialAPI.verifyKey(questionId, action === 'unverify'
        ? { action, reason: unverifyReason.trim() }
        : { action });
      setAskReason(false);
      setUnverifyReason('');
      onVerified(res.data);
      reload();
    } catch (err) {
      setActionError(describeEditorialError(err));
    } finally {
      setBusy('');
    }
  }

  async function markReviewed() {
    setBusy('review');
    setActionError(null);
    try {
      const res = await editorialAPI.reviewExplanation(questionId);
      onReviewed(res.data.updated_at);
      reload();
    } catch (err) {
      setActionError(describeEditorialError(err));
    } finally {
      setBusy('');
    }
  }

  const link = reviewQueueLink(questionId);
  const audit = data?.audit ?? null;
  const auditStatus = audit?.status || data?.answer_key_status || 'unaudited';
  const explanation = data?.explanation;
  const verification = data?.verification;

  return (
    <section aria-labelledby={`${ids}-title`} className="min-w-0 space-y-3 rounded-lg border border-border bg-card p-3 text-foreground">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <h3 id={`${ids}-title`} className="text-sm font-semibold">Key and explanation provenance</h3>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={reload} disabled={loading} aria-label="Reload provenance">
          {loading ? <Loader2 className="animate-spin" aria-hidden="true" /> : 'Reload'}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {loading && !data && <p className="text-sm text-muted-foreground">Loading…</p>}

      {data && (
        <>
          <div className="space-y-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Answer key</h4>
            <div className={rowClass}>
              <span>Stored key <strong>{data.correct_answer || 'not set'}</strong></span>
              <Badge variant={statusTone(auditStatus)} title={STATUS_HINTS[auditStatus as AuditStatus] ?? ''}>
                {auditStatusLabel(auditStatus)}
              </Badge>
              {audit?.status_reason && <span className="text-xs text-muted-foreground">{signalLabel(audit.status_reason)}</span>}
              {audit?.is_stale && <span className="text-xs text-amber-700 dark:text-amber-400">audit out of date</span>}
            </div>
            {audit?.suggested_key && audit.suggested_key !== data.correct_answer && (
              <p className="text-xs">
                The audit points to <strong>{audit.suggested_key}</strong>
                {audit.suggested_from ? ` (${signalLabel(audit.suggested_from)})` : ''}. It never changes a key by itself.
              </p>
            )}
            {audit && audit.open_signals.length > 0 && (
              <p className="break-words text-xs text-muted-foreground">Open: {audit.open_signals.map(signalLabel).join(' · ')}</p>
            )}
            {audit?.audited_at && <p className="text-xs text-muted-foreground">Audited {formatWhen(audit.audited_at)}</p>}
            <p className="text-xs">
              <Link href={link.href} className="font-medium text-primary underline-offset-2 hover:underline">Open the review queue</Link>
              <span className="text-muted-foreground"> — {link.hint}</span>
            </p>
          </div>

          <div className="space-y-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Key confirmation</h4>
            <p className="text-sm">
              {verification?.verified_by
                ? <>Confirmed by <strong>{verification.verified_by}</strong>{verification.verified_at ? ` on ${formatWhen(verification.verified_at)}` : ''}.</>
                : 'Not confirmed in the editor.'}
              {' '}
              <span className="text-xs text-muted-foreground">
                Student badge &ldquo;Verified by Admin&rdquo;: {verification?.is_verified_by_admin ? 'shown' : 'not shown'}.
              </span>
            </p>
            <p className="text-xs text-muted-foreground">
              Confirming without evidence makes the audit &ldquo;likely correct&rdquo;, never &ldquo;verified&rdquo;. To verify,
              cite strong evidence in a key change or in the review queue.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" disabled={!!busy || !data.correct_answer}
                onClick={() => verify('verify')} className="h-auto min-h-8 whitespace-normal py-1.5">
                {busy === 'verify' && <Loader2 className="animate-spin" aria-hidden="true" />} Confirm key {data.correct_answer || ''}
              </Button>
              <Button type="button" size="sm" variant="outline" disabled={!!busy}
                onClick={() => (askReason ? verify('unverify') : setAskReason(true))}
                className="h-auto min-h-8 whitespace-normal py-1.5">
                {busy === 'unverify' && <Loader2 className="animate-spin" aria-hidden="true" />}
                {askReason ? 'Send back to review now' : 'Send back to review'}
              </Button>
            </div>
            {askReason && (
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-medium">Why (optional, kept with the decision)</span>
                <textarea value={unverifyReason} onChange={(e) => setUnverifyReason(e.target.value)} rows={2}
                  className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm" />
              </label>
            )}
          </div>

          {explanation && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Explanation</h4>
              <div className={rowClass}>
                <Badge variant={explanationTone(explanation.status)}>
                  {EXPLANATION_STATUS_LABELS[explanation.status] ?? explanation.status}
                </Badge>
                {explanation.status_reason && <span className="text-xs text-muted-foreground">{explanation.status_reason}</span>}
              </div>
              {EXPLANATION_STATUS_HINTS[explanation.status] && (
                <p className="text-xs text-muted-foreground">{EXPLANATION_STATUS_HINTS[explanation.status]}</p>
              )}
              {explanation.has_text && (
                <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs">
                  <dt className="text-muted-foreground">Origin</dt><dd className="break-words">{originLabel(explanation.origin)}</dd>
                  <dt className="text-muted-foreground">Written for key</dt><dd>{explanation.for_key || 'not recorded'}</dd>
                  <dt className="text-muted-foreground">Reviewed</dt>
                  <dd className="break-words">
                    {explanation.reviewed_by
                      ? `${explanation.reviewed_by}${explanation.reviewed_at ? `, ${formatWhen(explanation.reviewed_at)}` : ''}`
                      : 'not yet'}
                  </dd>
                  <dt className="text-muted-foreground">Shown to students</dt>
                  <dd>{explanation.locked ? 'this text (locked against AI regeneration)' : 'an AI explanation may be shown ahead of it'}</dd>
                </dl>
              )}
              {explanation.has_text && (
                <Button type="button" size="sm" variant="outline" disabled={!!busy || !canMarkReviewed(explanation.status)}
                  onClick={markReviewed} className="h-auto min-h-8 whitespace-normal py-1.5"
                  title={canMarkReviewed(explanation.status) ? '' : 'Rewrite it for the current key first'}>
                  {busy === 'review' && <Loader2 className="animate-spin" aria-hidden="true" />} Mark the saved explanation reviewed
                </Button>
              )}
            </div>
          )}
          {actionError && <p className="text-sm text-destructive" role="alert">{actionError}</p>}

          <details className="text-sm">
            <summary className="flex cursor-pointer items-center gap-1.5 font-medium">
              <History className="h-4 w-4 text-muted-foreground" aria-hidden="true" /> Key history ({history?.length ?? keyChangeCount})
            </summary>
            {historyError && <p className="mt-1 text-xs text-destructive" role="alert">{historyError}</p>}
            {history && history.length === 0 && <p className="mt-1 text-xs text-muted-foreground">No key change recorded.</p>}
            {history && history.length > 0 && (
              <ol className="mt-1.5 space-y-1.5">
                {history.map((change) => (
                  <li key={change.id} className="min-w-0 rounded border border-border p-2 text-xs">
                    <p className="font-medium">{keyChangeLine(change)}</p>
                    <p className="text-muted-foreground">{formatWhen(change.changed_at)}</p>
                    <p className="whitespace-pre-wrap break-words">{change.reason}</p>
                    {change.evidence?.length > 0 && (
                      <p className="break-words text-muted-foreground">Evidence: {evidenceSummary(change.evidence)}</p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </details>
        </>
      )}
    </section>
  );
}
