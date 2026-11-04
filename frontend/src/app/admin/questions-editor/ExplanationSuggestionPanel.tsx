'use client';

import { useEffect, useId, useState } from 'react';
import { BookOpenCheck, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { editorialAPI, type ExplanationField, type ExplanationSuggestion } from '@/lib/editorialAPI';
import { LETTERS } from '@/lib/keyAudit';
import {
  SUGGESTION_STATUS_LABELS,
  acceptBlockedReason,
  acceptableFields,
  citationWhere,
  describeEditorialError,
  normalizeKey,
  optionSupportRows,
  suggestionMessage,
  suggestionTone,
} from './editorialRules';

/**
 * Evidence-first explanation help: POST /api/questions/<id>/explain-option/ for one option. The
 * server scores every option from the reference passages before comparing with the key; it answers
 * ok (with quotes), conflict (the evidence supports another option: no text), insufficient evidence
 * (also when the server has no reference store), figure missing, or failed. Only an "ok" suggestion
 * for the stored key can go into the editor; nothing is saved until the admin saves the explanation.
 */
export default function ExplanationSuggestionPanel({
  questionId,
  storedKey,
  storeAvailable,
  getDraft,
  onUseFields,
  onProposeKey,
  onSaveExplanation,
  unsavedSuggestion,
}: {
  questionId: number;
  storedKey: string;
  /** From the provenance payload; null while unknown. */
  storeAvailable: boolean | null;
  getDraft: () => Record<string, string>;
  onUseFields: (fields: Partial<Record<ExplanationField, string>>, suggestion: ExplanationSuggestion) => boolean;
  onProposeKey: (letter: string) => void;
  /** Saves the editor's explanation fields (with the used suggestion); resolves to an error or null. */
  onSaveExplanation: () => Promise<string | null>;
  /** True while text taken from a suggestion sits unsaved in the editor. */
  unsavedSuggestion: boolean;
}) {
  const ids = useId();
  const stored = normalizeKey(storedKey);
  const [selected, setSelected] = useState(stored || 'A');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<ExplanationSuggestion | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // A key change makes an earlier suggestion for the old key moot.
  useEffect(() => {
    setSuggestion((prev) => (prev && prev.stored_key !== stored ? null : prev));
    if (stored) setSelected(stored);
  }, [stored]);

  async function check(acknowledge = false) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await editorialAPI.explainOption(questionId, {
        selected,
        draft: getDraft(),
        acknowledge_conflict: acknowledge,
      });
      setSuggestion(res.data);
    } catch (err) {
      setError(describeEditorialError(err));
    } finally {
      setBusy(false);
    }
  }

  function use() {
    if (!suggestion) return;
    const fields: Partial<Record<ExplanationField, string>> = {};
    for (const item of acceptableFields(suggestion)) fields[item.field] = item.text;
    if (onUseFields(fields, suggestion)) {
      setNotice('Inserted into the Explanation field above (not saved yet). Edit it there, then save it here or with Save.');
    }
  }

  async function save() {
    setSaving(true);
    setNotice(null);
    setSaveError(null);
    const problem = await onSaveExplanation();
    setSaving(false);
    if (problem) setSaveError(problem);
    else setNotice('Explanation saved, with its provenance (for the current key).');
  }

  const blocked = suggestion ? acceptBlockedReason(suggestion, stored) : null;
  const fields = suggestion ? acceptableFields(suggestion) : [];
  const rows = suggestion ? optionSupportRows(suggestion) : [];
  const conflictKey = normalizeKey(suggestion?.conflict?.evidence_supports);

  return (
    <section aria-labelledby={`${ids}-title`} className="min-w-0 space-y-3 rounded-lg border border-border bg-card p-3 text-foreground">
      <div className="flex flex-wrap items-center gap-2">
        <BookOpenCheck className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <h3 id={`${ids}-title`} className="text-sm font-semibold">Check the evidence for an option</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        Evidence first: the reference passages are scored for every option before they are compared with the key. A
        suggestion only quotes stored passages (no AI-written book, page or quote). Nothing is saved until you save the
        explanation.
        {storeAvailable === false && ' This server has no reference store: every check will say there is not enough evidence.'}
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <fieldset>
          <legend className="mb-1 text-sm font-medium">Option to check</legend>
          <div role="radiogroup" aria-label="Option to check" className="flex flex-wrap gap-2">
            {LETTERS.map((letter) => (
              <label key={letter}
                className={`flex min-w-11 cursor-pointer items-center justify-center rounded-md border px-3 py-1.5 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring ${
                  selected === letter ? 'border-primary bg-primary/10 font-semibold' : 'border-border'
                }`}>
                <input type="radio" name={`${ids}-option`} value={letter} checked={selected === letter}
                  onChange={() => setSelected(letter)} className="sr-only" />
                {letter}
                {letter === stored && <span className="ml-1 text-[10px] font-normal text-muted-foreground">key</span>}
              </label>
            ))}
          </div>
        </fieldset>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => check(false)}
          className="h-auto min-h-8 whitespace-normal py-1.5">
          {busy && <Loader2 className="animate-spin" aria-hidden="true" />} Check option {selected}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}

      {suggestion && (
        <div className="min-w-0 space-y-2 rounded-md border border-border p-2.5" aria-live="polite">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={suggestionTone(suggestion.status)}>{SUGGESTION_STATUS_LABELS[suggestion.status] ?? suggestion.status}</Badge>
            <span className="text-xs text-muted-foreground">
              option {suggestion.for_key}{suggestion.stored_key ? ` · key ${suggestion.stored_key}` : ''}
              {suggestion.used_draft ? ' · unsaved text checked' : ''}
            </span>
          </div>
          <p className="text-sm">{suggestionMessage(suggestion)}</p>

          {suggestion.status === 'conflict' && conflictKey && conflictKey !== stored && (
            <Button type="button" size="sm" variant="outline" onClick={() => onProposeKey(conflictKey)}
              className="h-auto min-h-8 whitespace-normal py-1.5 text-left">
              Propose {conflictKey} in the key-change box
            </Button>
          )}
          {suggestion.status === 'ok' && stored && suggestion.for_key !== stored && (
            <Button type="button" size="sm" variant="outline" onClick={() => onProposeKey(suggestion.for_key)}
              className="h-auto min-h-8 whitespace-normal py-1.5 text-left">
              Propose {suggestion.for_key} in the key-change box
            </Button>
          )}
          {suggestion.status === 'conflict' && !suggestion.conflict?.acknowledged && (
            <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => check(true)}
              className="h-auto min-h-8 whitespace-normal py-1.5 text-left">
              Also show the passages found for option {suggestion.for_key}
            </Button>
          )}

          {rows.some((r) => r.support > 0) && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <caption className="mb-1 text-left text-muted-foreground">
                  Retrieval support by option (more matching reference text scores higher; not a verdict)
                </caption>
                <thead className="text-muted-foreground">
                  <tr><th scope="col" className="pr-2">Option</th><th scope="col" className="pr-2">Support</th><th scope="col">Passages</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.letter} className={r.best ? 'font-semibold' : ''}>
                      <td className="pr-2">{r.letter}{r.stored ? ' (key)' : ''}{r.selected ? ' (checked)' : ''}</td>
                      <td className="pr-2">{r.support.toFixed(2)}</td>
                      <td>{r.passages}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {suggestion.citations.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold">Reference passages</p>
              <ul className="space-y-1.5">
                {suggestion.citations.map((c) => (
                  <li key={c.chunk_key} className="min-w-0 rounded border border-border p-2 text-xs">
                    <p className="break-words font-medium">{citationWhere(c)}</p>
                    <blockquote className="mt-0.5 break-words italic text-muted-foreground">&ldquo;{c.snippet}&rdquo;</blockquote>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {suggestion.status === 'ok' && fields.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold">Suggested text</p>
              {fields.map((f) => (
                <div key={f.field} className="min-w-0">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{f.label}</p>
                  <p className="whitespace-pre-wrap break-words rounded bg-muted/50 p-2 text-xs">{f.text}</p>
                </div>
              ))}
            </div>
          )}

          {suggestion.status === 'ok' && (
            blocked
              ? <p className="text-xs text-amber-800 dark:text-amber-300">{blocked}</p>
              : (
                <Button type="button" size="sm" onClick={use} className="h-auto min-h-8 whitespace-normal py-1.5">
                  Use in the editor
                </Button>
              )
          )}
        </div>
      )}

      {unsavedSuggestion && (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="success" disabled={saving} onClick={save}
            className="h-auto min-h-8 whitespace-normal py-1.5">
            {saving && <Loader2 className="animate-spin" aria-hidden="true" />} Save explanation
          </Button>
          <span className="text-xs text-muted-foreground">Saves the explanation fields as they are in the editor now.</span>
        </div>
      )}
      {saveError && <p className="text-sm text-destructive" role="alert">{saveError}</p>}
      {notice && <p className="text-xs text-muted-foreground" role="status">{notice}</p>}
    </section>
  );
}
