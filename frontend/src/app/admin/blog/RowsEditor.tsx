'use client';

import React, { useId } from 'react';
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export interface RowColumn<R> {
    key: keyof R & string;
    label: string;
    placeholder?: string;
    multiline?: boolean;
    type?: 'text' | 'date' | 'url';
    /** Grid width on wide screens. */
    wide?: boolean;
}

interface RowsEditorProps<R> {
    legend: string;
    hint?: string;
    rows: R[];
    columns: RowColumn<R>[];
    blank: R;
    addLabel: string;
    error?: string;
    onChange: (rows: R[]) => void;
    /** Extra controls next to "Add" (e.g. "Build from headings"). */
    actions?: React.ReactNode;
}

const INPUT = 'w-full min-w-0 rounded-md border border-border bg-background px-2.5 py-1.5 text-sm text-foreground';

/** An editable list of small records (FAQs, TOC entries, references, revisions). */
export default function RowsEditor<R extends Record<string, string>>({
    legend, hint, rows, columns, blank, addLabel, error, onChange, actions,
}: RowsEditorProps<R>) {
    const baseId = useId();
    const update = (index: number, key: keyof R, value: string) =>
        onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
    const move = (index: number, delta: number) => {
        const target = index + delta;
        if (target < 0 || target >= rows.length) return;
        const next = rows.slice();
        [next[index], next[target]] = [next[target], next[index]];
        onChange(next);
    };

    return (
        <fieldset className="min-w-0 rounded-lg border border-border p-3">
            <legend className="px-1 text-sm font-semibold text-foreground">{legend} <span className="font-normal text-muted-foreground">({rows.length})</span></legend>
            {hint && <p className="mb-2 text-xs text-muted-foreground">{hint}</p>}
            <ol className="space-y-2">
                {rows.map((row, index) => (
                    <li key={index} className="rounded-md border border-border bg-muted/30 p-2">
                        <div className="grid min-w-0 gap-2 sm:grid-cols-2">
                            {columns.map((column) => {
                                const id = `${baseId}-${index}-${column.key}`;
                                const common = {
                                    id,
                                    value: row[column.key] ?? '',
                                    placeholder: column.placeholder,
                                    className: INPUT,
                                };
                                return (
                                    <div key={column.key} className={`min-w-0 ${column.wide || column.multiline ? 'sm:col-span-2' : ''}`}>
                                        <label htmlFor={id} className="mb-0.5 block text-xs text-muted-foreground">
                                            {column.label} {index + 1}
                                        </label>
                                        {column.multiline ? (
                                            <textarea {...common} rows={3}
                                                onChange={(e) => update(index, column.key, e.target.value)} />
                                        ) : (
                                            <input {...common} type={column.type ?? 'text'}
                                                onChange={(e) => update(index, column.key, e.target.value)} />
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                        <div className="mt-1.5 flex flex-wrap justify-end gap-1">
                            <Button type="button" variant="ghost" size="sm" onClick={() => move(index, -1)} disabled={index === 0}
                                aria-label={`Move ${legend} item ${index + 1} up`}>
                                <ArrowUp className="h-4 w-4" />
                            </Button>
                            <Button type="button" variant="ghost" size="sm" onClick={() => move(index, 1)} disabled={index === rows.length - 1}
                                aria-label={`Move ${legend} item ${index + 1} down`}>
                                <ArrowDown className="h-4 w-4" />
                            </Button>
                            <Button type="button" variant="ghost" size="sm" className="text-destructive"
                                onClick={() => onChange(rows.filter((_, i) => i !== index))}
                                aria-label={`Remove ${legend} item ${index + 1}`}>
                                <Trash2 className="h-4 w-4" />
                            </Button>
                        </div>
                    </li>
                ))}
            </ol>
            <div className="mt-2 flex flex-wrap gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => onChange([...rows, { ...blank }])}>
                    <Plus className="h-4 w-4" /> {addLabel}
                </Button>
                {actions}
            </div>
            {error && <p className="mt-2 text-xs text-destructive" role="alert">{error}</p>}
        </fieldset>
    );
}
