'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Lock, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { keyAuditAPI } from '@/lib/api';
import {
  LETTERS,
  RESOLUTIONS,
  STATUS_HINTS,
  STATUS_LABELS,
  type AuditDetail,
  type EvidenceItem,
  type Resolution,
  describeError,
  expectedStatus,
  optionText,
  resolvePayload,
  severityTone,
  signalLabel,
  statusTone,
} from '@/lib/keyAudit';
import EvidenceEditor from './EvidenceEditor';

export interface ResolvedResult {
  question_id: number;
  audit_status: string;
  current_key: string;
}

export default function AuditDetailPanel({
  questionId,
  onResolved,
  onClose,
}: {
  questionId: number;
  onResolved: (result: ResolvedResult) => void;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<AuditDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [claimError, setClaimError] = useState<string | null>(null);
  const [resolution, setResolution] = useState<Resolution>('key_confirmed');
  const [newKey, setNewKey] = useState('');
  const [reason, setReason] = useState('');
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [explanation, setExplanation] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await keyAuditAPI.detail(questionId);
      const data = res.data as AuditDetail;
      setDetail(data);
      setExplanation(data.question.explanation || '');
      if (data.suggested_key) {
        setNewKey(data.suggested_key);
      }
    } catch (err) {
      setLoadError(describeError(err));
    } finally {
      setLoading(false);
    }
  }, [questionId]);

  // Claim the question while it is open, release it when another one is opened.
  useEffect(() => {
    let active = true;
    setClaimError(null);
    setEvidence([]);
    setReason('');
    setSubmitError(null);
    setResolution('key_confirmed');
    keyAuditAPI.claim(questionId).catch((err) => { if (active) setClaimError(describeError(err)); });
    load();
    return () => {
      active = false;
      keyAuditAPI.release(questionId).catch(() => { /* expired or never held */ });
    };
  }, [questionId, load]);

  const willBe = useMemo(() => expectedStatus({ resolution, evidence }), [resolution, evidence]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!detail) return;
    const built = resolvePayload({
      resolution, reason, newKey, expectedKey: detail.question.correct_answer?.trim().toUpperCase().slice(0, 1) || '',
      evidence, explanation,
    });
    if ('error' in built) {
      setSubmitError(built.error);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await keyAuditAPI.resolve(questionId, built.body);
      onResolved(res.data as ResolvedResult);
    } catch (err) {
      setSubmitError(describeError(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !detail) {
    return <div className="flex items-center gap-2 p-4 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>;
  }
  if (loadError || !detail) {
    return <p className="p-4 text-destructive" role="alert">{loadError || 'Not found.'}</p>;
  }

  const q = detail.question;
  const stored = (q.correct_answer || '').trim().toUpperCase().slice(0, 1);
  const openSignals = detail.signals.filter((s) => s.opens_review && !s.settled_by_review);
  const otherSignals = detail.signals.filter((s) => !(s.opens_review && !s.settled_by_review));
  const blocked = !!claimError;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Question #{q.id}</h2>
          <p className="text-xs text-muted-foreground">
            {q.exam_type} {q.year || ''} · {q.subject}{q.topic ? ` / ${q.topic}` : ''} · source: {q.source || 'unknown'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusTone(detail.status)} title={STATUS_HINTS[detail.status]}>{STATUS_LABELS[detail.status] ?? detail.status}</Badge>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-accent"><X className="h-4 w-4" /></button>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{signalLabel(detail.status_reason)}</p>
      {claimError && (
        <p className="flex items-center gap-1.5 rounded-md bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:bg-amber-500/15 dark:text-amber-300" role="status">
          <Lock className="h-4 w-4" /> {claimError}
        </p>
      )}

      <section aria-label="Question" className="space-y-2 rounded-lg border border-border p-3">
        <p className="whitespace-pre-wrap text-sm">{q.question_text}</p>
        <ol className="space-y-1">
          {LETTERS.map((letter) => {
            const isStored = letter === stored;
            const isSuggested = letter === detail.suggested_key;
            return (
              <li key={letter} className={`flex gap-2 rounded px-2 py-1 text-sm ${isStored ? 'bg-sky-100 dark:bg-sky-500/15' : ''} ${isSuggested ? 'ring-1 ring-amber-500' : ''}`}>
                <span className="font-semibold">{letter}.</span>
                <span className="flex-1 whitespace-pre-wrap">{optionText(q, letter) || <em className="text-muted-foreground">(empty)</em>}</span>
                {isStored && <span className="text-xs font-semibold text-sky-800 dark:text-sky-300">stored key</span>}
                {isSuggested && <span className="text-xs font-semibold text-amber-700 dark:text-amber-400">suggested ({signalLabel(detail.evidence_summary.suggested_from)})</span>}
              </li>
            );
          })}
        </ol>
        {q.image_ids.length > 0 && <p className="text-xs text-muted-foreground">{q.image_ids.length} figure(s) attached (ids {q.image_ids.join(', ')}).</p>}
        {detail.original_key && detail.original_key !== stored && (
          <p className="text-xs text-muted-foreground">Original key: {detail.original_key}</p>
        )}
        {q.explanation && (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">Explanation</summary>
            <p className="mt-1 whitespace-pre-wrap">{q.explanation}</p>
          </details>
        )}
      </section>

      <section aria-label="Signals" className="space-y-1.5">
        <h3 className="text-sm font-semibold">Signals</h3>
        {openSignals.length === 0 && <p className="text-xs text-muted-foreground">No open risk signal.</p>}
        {openSignals.map((s, i) => (
          <div key={`o${i}`} className="rounded-md border border-border p-2 text-sm">
            <Badge variant={severityTone(s.severity)} className="mr-2">{signalLabel(s.code)}</Badge>
            {s.suggested_key && <span className="mr-2 text-xs font-semibold">→ {s.suggested_key}</span>}
            <span className="text-muted-foreground">{s.detail}</span>
          </div>
        ))}
        {otherSignals.length > 0 && (
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">{otherSignals.length} other signal(s)</summary>
            <ul className="mt-1 space-y-1">
              {otherSignals.map((s, i) => (
                <li key={`x${i}`}>{signalLabel(s.code)}{s.settled_by_review ? ' (settled by an admin decision)' : ''}: {s.detail}</li>
              ))}
            </ul>
          </details>
        )}
      </section>

      {detail.source_keys.length > 0 && (
        <section aria-label="Printed source keys" className="space-y-1.5">
          <h3 className="text-sm font-semibold">Printed source keys <span className="font-normal text-muted-foreground">(tier 4: the document the question came from)</span></h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted-foreground">
                <tr><th className="py-1 pr-2">File</th><th className="pr-2">Question</th><th className="pr-2">Prints</th><th className="pr-2">Here</th><th className="pr-2">Check</th></tr>
              </thead>
              <tbody>
                {detail.source_keys.map((row) => (
                  <tr key={row.id} className="border-t border-border">
                    <td className="py-1 pr-2">{row.source_file}{row.chapter ? ` · ${row.chapter}` : ''}</td>
                    <td className="pr-2">PDF p. {row.question_page}, Q{row.question_number}{row.answer_page ? ` (answer p. ${row.answer_page})` : ''}</td>
                    <td className="pr-2 font-semibold">{row.printed_letter}</td>
                    <td className={`pr-2 font-semibold ${row.letter !== stored ? 'text-destructive' : 'text-emerald-700 dark:text-emerald-400'}`}>{row.letter}</td>
                    <td className="pr-2">{row.confident ? 'stem found, options matched' : row.located ? 'options not matched' : 'stem not found'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {detail.reviews.length > 0 && (
        <section aria-label="Reviews" className="space-y-1.5">
          <h3 className="text-sm font-semibold">Reviews</h3>
          {detail.reviews.map((r, i) => (
            <div key={i} className="rounded-md border border-border p-2 text-sm">
              <p className="text-xs font-semibold">{r.label}</p>
              <p>
                {r.verdict}{r.best_option ? ` · picks ${r.best_option}` : ''}{r.confidence ? ` · ${r.confidence} confidence` : ''}
                {r.issues?.length ? ` · ${r.issues.join(', ').replace(/_/g, ' ')}` : ''}
              </p>
              {r.reason && <p className="text-xs text-muted-foreground">{r.reason}</p>}
            </div>
          ))}
        </section>
      )}

      {(detail.key_changes.length > 0 || detail.resolutions.length > 0) && (
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">History</summary>
          <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
            {detail.key_changes.map((c) => (
              <li key={`k${c.id}`}>{new Date(c.changed_at).toLocaleString()}: key {c.old_key || '–'} → {c.new_key} by {c.changed_by || 'unknown'} ({c.source}): {c.reason}</li>
            ))}
            {detail.resolutions.map((r) => (
              <li key={`r${r.id}`}>{new Date(r.resolved_at).toLocaleString()}: {r.resolution} by {r.resolved_by || 'unknown'}: {r.reason}</li>
            ))}
          </ul>
        </details>
      )}

      <form onSubmit={submit} className="space-y-3 rounded-lg border border-border p-3" aria-label="Decision">
        <h3 className="text-sm font-semibold">Decision</h3>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Action</span>
          <select value={resolution} onChange={(e) => setResolution(e.target.value as Resolution)} disabled={blocked}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm">
            {RESOLUTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <span className="mt-1 block text-xs text-muted-foreground">{RESOLUTIONS.find((r) => r.value === resolution)?.hint}</span>
        </label>
        {resolution === 'key_changed' && (
          <div role="radiogroup" aria-label="New key" className="flex gap-2">
            {LETTERS.filter((l) => l !== stored).map((letter) => (
              <label key={letter} className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm ${newKey === letter ? 'border-primary bg-primary/10 font-semibold' : 'border-border'}`}>
                <input type="radio" name="new-key" value={letter} checked={newKey === letter} onChange={() => setNewKey(letter)} className="sr-only" />
                {letter}
              </label>
            ))}
          </div>
        )}
        {resolution === 'explanation_fixed' && (
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Corrected explanation (for key {stored})</span>
            <textarea value={explanation} onChange={(e) => setExplanation(e.target.value)} rows={6}
              className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm" />
          </label>
        )}
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Reason</span>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} disabled={blocked}
            placeholder="Why (at least 10 characters). Kept with the decision."
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm" />
        </label>
        <EvidenceEditor items={evidence} onChange={setEvidence} sourceKeys={detail.source_keys} />
        {willBe && <p className="text-xs text-muted-foreground">After this decision the audit will show: <strong>{STATUS_LABELS[willBe as keyof typeof STATUS_LABELS]}</strong>.</p>}
        {submitError && <p className="text-sm text-destructive" role="alert">{submitError}</p>}
        <Button type="submit" disabled={submitting || blocked}>
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />} Record decision
        </Button>
      </form>
    </div>
  );
}
