'use client';

import React, { useEffect, useId, useState } from 'react';
import { KeyRound, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { editorialAPI, type KeyChangeResult } from '@/lib/editorialAPI';
import { LETTERS, STATUS_LABELS, statusTone, type EvidenceItem, type SourceKeyRow } from '@/lib/keyAudit';
import EvidenceEditor from '../review-queue/EvidenceEditor';
import {
  MIN_REASON_CHARS,
  auditStatusLabel,
  describeEditorialError,
  keyChangeOutcome,
  keyChangeOutcomeText,
  keyChangePayload,
  keyChangeProblems,
  normalizeKey,
} from './editorialRules';

const inputClass =
  'w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring';

/**
 * Change (or first set) a question's answer key: POST /api/questions/<id>/change-key/ with a reason and
 * evidence. The only way the editor changes a key: the old key, the admin, the reason and the evidence
 * are recorded (AnswerKeyChange), and the answer-key audit re-classifies the question. With strong
 * evidence the result is "verified", otherwise "likely correct" -- shown before the change is made.
 */
export default function KeyChangeBox({
  questionId,
  storedKey,
  sourceKeys,
  proposedKey,
  disabled,
  onChanged,
}: {
  questionId: number;
  storedKey: string;
  sourceKeys: SourceKeyRow[];
  /** A letter another panel suggests (e.g. the evidence check found support for it). */
  proposedKey?: string;
  disabled?: boolean;
  onChanged: (result: KeyChangeResult) => void;
}) {
  const ids = useId();
  const stored = normalizeKey(storedKey);
  const [newKey, setNewKey] = useState('');
  const [reason, setReason] = useState('');
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    const key = normalizeKey(proposedKey);
    if (key && key !== stored) {
      setNewKey(key);
      setDone(null);
    }
  }, [proposedKey, stored]);

  const problems = keyChangeProblems({ storedKey: stored, newKey, reason, evidence });
  const outcome = keyChangeOutcome(evidence);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    const built = keyChangePayload({ storedKey: stored, newKey, reason, evidence });
    if ('error' in built) {
      setError(built.error);
      return;
    }
    const verb = stored ? `Change the key from ${stored} to ${built.body.new_key}` : `Set the key to ${built.body.new_key}`;
    if (!window.confirm(`${verb}? Students' answers are marked against the new key from now on.`)) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const res = await editorialAPI.changeKey(questionId, built.body);
      const result = res.data;
      setDone(
        `Key ${result.old_key || '(none)'} → ${result.new_key}. The audit now shows: ${auditStatusLabel(result.answer_key_status)}.`
        + (result.explanation?.status === 'stale' || result.explanation?.status === 'conflict'
          ? ' The explanation was written for the old key: rewrite it.'
          : ''),
      );
      setNewKey('');
      setReason('');
      setEvidence([]);
      setTouched(false);
      onChanged(result);
    } catch (err) {
      setError(describeEditorialError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} aria-labelledby={`${ids}-title`}
      className="min-w-0 space-y-3 rounded-lg border border-border bg-card p-3 text-foreground">
      <div className="flex flex-wrap items-center gap-2">
        <KeyRound className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <h3 id={`${ids}-title`} className="text-sm font-semibold">{stored ? 'Change the answer key' : 'Set the answer key'}</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        Stored key: <strong className="text-foreground">{stored || 'not set'}</strong>. A key changes only here or in the
        review queue, with a reason; the old key, you, the reason and the evidence are kept in the key history.
      </p>

      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">New key</legend>
        <div role="radiogroup" aria-label="New key" className="flex flex-wrap gap-2">
          {LETTERS.map((letter) => {
            const isStored = letter === stored;
            return (
              <label key={letter}
                className={`flex min-w-11 cursor-pointer items-center justify-center rounded-md border px-3 py-1.5 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring ${
                  newKey === letter ? 'border-primary bg-primary/10 font-semibold' : 'border-border'
                } ${isStored ? 'cursor-not-allowed opacity-50' : ''}`}>
                <input type="radio" name={`${ids}-new-key`} value={letter} checked={newKey === letter} disabled={isStored || disabled}
                  onChange={() => { setNewKey(letter); setDone(null); }} className="sr-only" />
                {letter}
                {isStored && <span className="sr-only"> (stored key)</span>}
              </label>
            );
          })}
        </div>
      </fieldset>

      <label className="block text-sm">
        <span className="mb-1 block font-medium">Reason</span>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} disabled={disabled}
          placeholder={`Why the key is wrong (at least ${MIN_REASON_CHARS} characters). Kept in the history.`}
          className={inputClass} />
      </label>

      <EvidenceEditor items={evidence} onChange={setEvidence} sourceKeys={sourceKeys} />

      <div className="text-xs text-muted-foreground" aria-live="polite">
        After the change the audit will show{' '}
        <Badge variant={statusTone(outcome)}>{STATUS_LABELS[outcome]}</Badge>{' '}
        {keyChangeOutcomeText(evidence)} An official key that names another option still sends it back to review.
      </div>

      {touched && problems.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-destructive" role="alert">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {done && <p className="rounded-md bg-emerald-100 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-500/15 dark:text-emerald-300" role="status">{done}</p>}

      <Button type="submit" size="sm" disabled={busy || disabled || (touched && problems.length > 0)}
        className="h-auto min-h-8 whitespace-normal py-1.5 text-left">
        {busy && <Loader2 className="animate-spin" aria-hidden="true" />}
        {normalizeKey(newKey)
          ? `${stored ? 'Change key to' : 'Set key to'} ${normalizeKey(newKey)}`
          : stored ? 'Change the key' : 'Set the key'}
      </Button>
    </form>
  );
}
