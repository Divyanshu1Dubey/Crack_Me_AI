'use client';

import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import {
  EVIDENCE_KINDS,
  evidenceError,
  type EvidenceItem,
  type EvidenceKind,
  type SourceKeyRow,
  sourceKeyEvidence,
} from '@/lib/keyAudit';

const inputClass =
  'w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring';

/** The evidence list of a decision. Strong kinds (official key, errata, guideline, passage) make a
 *  confirmation "verified"; a printed source key or a note does not. */
export default function EvidenceEditor({
  items,
  onChange,
  sourceKeys,
}: {
  items: EvidenceItem[];
  onChange: (items: EvidenceItem[]) => void;
  sourceKeys: SourceKeyRow[];
}) {
  const update = (index: number, patch: Partial<EvidenceItem>) =>
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));
  const add = (kind: EvidenceKind) => onChange([...items, { kind }]);
  const cited = new Set(items.filter((i) => i.kind === 'source_key').map((i) => i.source_key_id));

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">Evidence</legend>
      {items.length === 0 && (
        <p className="text-xs text-muted-foreground">
          None yet. Without strong evidence a confirmed or changed key is &ldquo;likely correct&rdquo;, not &ldquo;verified&rdquo;.
        </p>
      )}
      {items.map((item, index) => {
        const spec = EVIDENCE_KINDS.find((k) => k.kind === item.kind);
        const error = evidenceError(item);
        const id = `ev-${index}`;
        return (
          <div key={index} className="space-y-1.5 rounded-md border border-border p-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold">
                {spec?.label ?? item.kind}
                {spec?.strong ? <span className="ml-1 text-emerald-700 dark:text-emerald-400">(strong)</span> : null}
              </span>
              <button type="button" onClick={() => remove(index)} aria-label="Remove this evidence"
                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            {item.kind === 'source_key' ? (
              <p className="text-xs text-muted-foreground">
                {item.source_title} {item.page_label} (printed source key #{item.source_key_id})
              </p>
            ) : item.kind === 'note' ? (
              <textarea id={`${id}-text`} aria-label="Note" className={inputClass} rows={2} value={item.text ?? ''}
                placeholder="Your reasoning (shown in the history; not evidence)"
                onChange={(e) => update(index, { text: e.target.value })} />
            ) : (
              <div className="grid gap-1.5 sm:grid-cols-2">
                <input aria-label="Source title" className={inputClass} value={item.source_title ?? ''}
                  placeholder={item.kind === 'passage' ? 'Book title, edition' : 'e.g. UPSC CMS 2023 Paper I official key'}
                  onChange={(e) => update(index, { source_title: e.target.value })} />
                {item.kind === 'guideline_url' && (
                  <input aria-label="Link" className={inputClass} value={item.url ?? ''} placeholder="https://"
                    onChange={(e) => update(index, { url: e.target.value })} />
                )}
                {item.kind === 'passage' && (
                  <input aria-label="Page" className={inputClass} value={item.page_label ?? ''} placeholder="Page (printed number)"
                    onChange={(e) => update(index, { page_label: e.target.value })} />
                )}
                {item.kind === 'passage' && (
                  <textarea aria-label="Quoted sentence" className={`${inputClass} sm:col-span-2`} rows={2} value={item.quote ?? ''}
                    placeholder="The sentence that states the answer, copied exactly"
                    onChange={(e) => update(index, { quote: e.target.value })} />
                )}
              </div>
            )}
            {error && <p className="text-xs text-destructive" role="alert">{error}</p>}
          </div>
        );
      })}
      <div className="flex flex-wrap gap-1.5">
        {EVIDENCE_KINDS.filter((k) => k.kind !== 'source_key').map((k) => (
          <button key={k.kind} type="button" onClick={() => add(k.kind)}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-accent">
            <Plus className="h-3 w-3" /> {k.label}
          </button>
        ))}
        {sourceKeys.filter((row) => !cited.has(row.id)).map((row) => (
          <button key={row.id} type="button" onClick={() => onChange([...items, sourceKeyEvidence(row)])}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-accent">
            <Plus className="h-3 w-3" /> Cite printed key {row.letter} ({row.source_file}, PDF p. {row.question_page})
          </button>
        ))}
      </div>
    </fieldset>
  );
}
