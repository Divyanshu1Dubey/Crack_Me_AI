'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { questionsAPI } from '@/lib/api';
import { resolveImageTokens, type QuestionImageLike } from '@/lib/imageTokens';

interface QuestionEditModalProps {
  question: any;
  images: QuestionImageLike[];
  onClose: () => void;
  onSaved: (updated: any) => void;
}

export default function QuestionEditModal({ question, images: initialImages, onClose, onSaved }: QuestionEditModalProps) {
  const [form, setForm] = useState({
    question_text: question.question_text ?? '',
    option_a: question.option_a ?? '',
    option_b: question.option_b ?? '',
    option_c: question.option_c ?? '',
    option_d: question.option_d ?? '',
    correct_answer: question.correct_answer ?? 'A',
    explanation: question.explanation ?? '',
    mnemonic: question.mnemonic ?? '',
    concept_explanation: question.concept_explanation ?? '',
    difficulty: question.difficulty ?? 'medium',
    topic: question.topic ?? null,
    needs_review: !!question.needs_review,
    is_dropped: !!question.is_dropped,
    is_controversial: !!question.is_controversial,
  });
  const [images, setImages] = useState<QuestionImageLike[]>(initialImages);
  const [updatedAt, setUpdatedAt] = useState<string>(question.updated_at ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<any | null>(null);
  const [uploadingField, setUploadingField] = useState<string | null>(null);
  const fieldRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});

  // Pre-compute resolved image HTML for every field that supports images.
  // The public practice page mirrors this same pattern.
  const fieldsWithImages = [
    { key: 'question_text', label: 'Question Text' },
    { key: 'option_a', label: 'Option A' },
    { key: 'option_b', label: 'Option B' },
    { key: 'option_c', label: 'Option C' },
    { key: 'option_d', label: 'Option D' },
    { key: 'explanation', label: 'Explanation' },
    { key: 'mnemonic', label: 'Mnemonic' },
    { key: 'concept_explanation', label: 'Concept Explanation' },
  ] as const;

  const cacheKey = useMemo(
    () => `${question.id}:${images.map((i) => i.id).join('|')}`,
    [question.id, images],
  );

  const previewHtml = useMemo(
    () => resolveImageTokens(form.question_text, images, cacheKey),
    [form.question_text, images, cacheKey],
  );

  // Returns insert-image button — used across every text field so the
  // affordance is consistent and discoverable.
  function renderInsertImageButton(fieldKey: string) {
    const isUploading = uploadingField === fieldKey;
    return (
      <button
        type="button"
        onClick={() => insertImage(fieldKey)}
        disabled={isUploading}
        title="Upload an image and insert a token at the cursor position"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
      >
        <span aria-hidden>📷</span>
        {isUploading ? 'Uploading…' : 'Insert image'}
      </button>
    );
  }

  // Resolve the best-available src for an image. The upload endpoint returns
  // either `url` (Supabase public URL for admin uploads) or `file` (Django
  // media path for recall imports). The question-list serializer rewrites
  // both to the auth-gated `/api/questions/images/<id>/serve/` proxy, so
  // callers sometimes see only that relative path — prefer the absolute
  // URL when present.
  function imageSrc(img: QuestionImageLike): string {
    // Preference order (Bug #2026-07-27 admin editor "broken link" fix):
    //   1. `serve_url` (added by QuestionImageSerializer) — admin
    //      uploads use the public Supabase URL directly, recall
    //      imports use the auth-gated proxy. Either way it's reachable
    //      in production where `/media/` 404s.
    //   2. `img.url` — public URL stashed at upload/import time.
    //   3. `img.file` — raw ImageField URL. Mostly the same as
    //      `/media/recall_images/...`, kept as a last-ditch fallback.
    const extended = img as QuestionImageLike & { serve_url?: string };
    return (
      extended.serve_url ||
      img.url ||
      (typeof img.file === 'string' ? img.file : '') ||
      ''
    );
  }

  // Renders a small inline preview of any images referenced from `text`.
  // Helps the admin confirm what the public page will see.
  function renderInlinePreview(text: string) {
    const matches = text.matchAll(/\[\[img:(\d+)\]\]/g);
    const ids = new Set<number>();
    for (const m of matches) ids.add(parseInt(m[1], 10));
    if (ids.size === 0) return null;
    const referenced = images.filter((img) => ids.has(img.id));
    if (referenced.length === 0) return null;
    return (
      <div className="mt-2 flex flex-wrap gap-2">
        {referenced.map((img) => (
          <a
            key={img.id}
            href={imageSrc(img) || '#'}
            target="_blank"
            rel="noreferrer"
            className="block w-20 h-20 border rounded overflow-hidden bg-gray-50"
            title={`Image #${img.id}${img.caption ? ` — ${img.caption}` : ''}`}
          >
            {imageSrc(img) ? (
              <img
                src={imageSrc(img)}
                alt={img.caption || `image #${img.id}`}
                className="w-full h-full object-cover"
                onError={(e) => {
                  // Replace broken thumbnails with a labelled placeholder so
                  // the admin notices that the URL is unreachable instead of
                  // silently staring at a blank box.
                  (e.currentTarget as HTMLImageElement).style.display = 'none';
                  const parent = (e.currentTarget as HTMLImageElement).parentElement;
                  if (parent) parent.innerHTML = `<div class="w-full h-full flex items-center justify-center text-[10px] text-gray-500 text-center p-1">broken img #${img.id}</div>`;
                }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-[10px] text-gray-500 text-center p-1">
                no url for #{img.id}
              </div>
            )}
          </a>
        ))}
      </div>
    );
  }

  // Generic cursor-position text inserter. Reused by the markdown toolbar
  // and (via insertImage below) by image upload. `snippet` is the raw text
  // to drop in; if `wrap` is provided and the textarea has a selection,
  // the selection is wrapped and the cursor lands between the open/close
  // markers — same UX as a Notion-style formatting toolbar.
  function insertAtCursor(fieldKey: string, snippet: string, wrap?: { open: string; close: string; placeholder?: string }) {
    const ref = fieldRefs.current[fieldKey];
    const currentValue = (form as any)[fieldKey] ?? '';
    if (!ref) {
      const appended = wrap
        ? `${wrap.open}${wrap.placeholder ?? ''}${wrap.close}`
        : snippet;
      setForm({ ...form, [fieldKey]: currentValue + appended });
      return;
    }
    const start = ref.selectionStart ?? currentValue.length;
    const end = ref.selectionEnd ?? currentValue.length;
    const before = currentValue.slice(0, start);
    const after = currentValue.slice(end);
    if (wrap) {
      const selected = currentValue.slice(start, end);
      const inner = selected || wrap.placeholder || snippet;
      setForm({ ...form, [fieldKey]: `${before}${wrap.open}${inner}${wrap.close}${after}` });
      return;
    }
    setForm({ ...form, [fieldKey]: `${before}${snippet}${after}` });
  }

  /**
   * MarkdownToolbar — small strip of formatting buttons for image-aware text
   * fields. Uses `[[red]]…[[/red]]` and `[[u]]…[[/u]]` custom tokens which
   * `FormattedText.applyColorTokens` resolves at render time; the rest is
   * standard markdown already supported by `react-markdown@10`.
   *
   * Buttons:
   *   B / I    — wraps selection in ** / *
   *   H1 / H2  — prepends "# " / "## " at the cursor (line-start)
   *   list     — prepends "- " at the cursor (line-start)
   *   quote    — prepends "> " at the cursor (line-start)
   *   red      — wraps selection in [[red]]…[[/red]]
   *   underline— wraps selection in [[u]]…[[/u]]
   *   code     — wraps selection in `…`
   */
  function renderMarkdownToolbar(fieldKey: string) {
    const btnBase =
      'inline-flex items-center justify-center min-w-7 h-7 px-2 rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 hover:border-gray-400 text-xs font-semibold transition';
    return (
      <div className="flex flex-wrap gap-1 items-center" role="toolbar" aria-label={`Formatting toolbar for ${fieldKey}`}>
        <button type="button" title="Bold (**)" onClick={() => insertAtCursor(fieldKey, '', { open: '**', close: '**', placeholder: 'bold' })} className={btnBase}>B</button>
        <button type="button" title="Italic (*)" onClick={() => insertAtCursor(fieldKey, '', { open: '*', close: '*', placeholder: 'italic' })} className={btnBase}><span className="italic">I</span></button>
        <span className="w-px h-5 bg-gray-200 mx-1" aria-hidden />
        <button type="button" title="Heading 1 (#)" onClick={() => insertLineStart(fieldKey, '# ')} className={btnBase}>H1</button>
        <button type="button" title="Heading 2 (##)" onClick={() => insertLineStart(fieldKey, '## ')} className={btnBase}>H2</button>
        <button type="button" title="Bullet list (-)" onClick={() => insertLineStart(fieldKey, '- ')} className={btnBase}>•</button>
        <button type="button" title="Quote (>)" onClick={() => insertLineStart(fieldKey, '> ')} className={btnBase}>&ldquo;</button>
        <span className="w-px h-5 bg-gray-200 mx-1" aria-hidden />
        <button type="button" title="Code (`)" onClick={() => insertAtCursor(fieldKey, '', { open: '`', close: '`', placeholder: 'code' })} className={btnBase}>{`</>`}</button>
        <button type="button" title="Red highlight ([[red]])" onClick={() => insertAtCursor(fieldKey, '', { open: '[[red]]', close: '[[/red]]', placeholder: 'important' })} className={btnBase + ' text-red-700'}>red</button>
        <button type="button" title="Underline ([[u]])" onClick={() => insertAtCursor(fieldKey, '', { open: '[[u]]', close: '[[/u]]', placeholder: 'underline' })} className={btnBase + ' underline'}>U</button>
      </div>
    );
  }

  // Prepend `prefix` at the start of the current line where the cursor sits.
  // If the line already starts with the prefix (case-sensitive), do nothing
  // — keeps a second click from doubling up.
  function insertLineStart(fieldKey: string, prefix: string) {
    const ref = fieldRefs.current[fieldKey];
    const currentValue = (form as any)[fieldKey] ?? '';
    if (!ref) {
      setForm({ ...form, [fieldKey]: `${currentValue}\n${prefix}` });
      return;
    }
    const cursor = ref.selectionStart ?? currentValue.length;
    // Walk backwards to find the last `\n` (or start of string) before cursor.
    const before = currentValue.slice(0, cursor);
    const lastNl = before.lastIndexOf('\n');
    const lineStart = lastNl + 1;
    const lineRest = currentValue.slice(lineStart, currentValue.length);
    if (lineRest.startsWith(prefix)) {
      // Toggle off (remove prefix) if already prefixed — feels right for a toolbar.
      const newValue = currentValue.slice(0, lineStart) + lineRest.slice(prefix.length);
      setForm({ ...form, [fieldKey]: newValue });
      return;
    }
    const newValue = currentValue.slice(0, lineStart) + prefix + currentValue.slice(lineStart);
    setForm({ ...form, [fieldKey]: newValue });
  }

  async function insertImage(fieldKey: string) {
    const ref = fieldRefs.current[fieldKey];
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/webp,image/gif';
    setUploadingField(fieldKey);
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) {
        setUploadingField(null);
        return;
      }
      try {
        const res = await questionsAPI.uploadImage({ questionId: question.id, file });
        const img = res.data as QuestionImageLike;
        const newImages = [...images, img];
        setImages(newImages);
        const token = `[[img:${img.id}]]`;
        if (ref) {
          const start = ref.selectionStart ?? ref.value.length;
          const end = ref.selectionEnd ?? ref.value.length;
          const currentValue = (form as any)[fieldKey] ?? '';
          setForm({ ...form, [fieldKey]: currentValue.slice(0, start) + token + currentValue.slice(end) });
        } else {
          // No ref available — append to the end of the field.
          setForm({ ...form, [fieldKey]: ((form as any)[fieldKey] ?? '') + token });
        }
      } catch (e: any) {
        setError('Failed to upload image: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
      } finally {
        setUploadingField(null);
      }
    };
    input.click();
  }

  async function deleteImage(id: number) {
    if (!confirm('Delete this image permanently?')) return;
    try {
      await questionsAPI.deleteImage(id);
      setImages(images.filter((i) => i.id !== id));
      const tokenRe = new RegExp(`\\[\\[img:${id}\\]\\]`, 'g');
      const updated: any = { ...form };
      for (const k of fieldsWithImages.map((f) => f.key)) {
        const v = (form as any)[k];
        if (typeof v === 'string') updated[k] = v.replace(tokenRe, '');
      }
      setForm(updated);
    } catch (e: any) {
      setError('Failed to delete image: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
    }
  }

  async function moveImage(id: number, delta: number) {
    const idx = images.findIndex((i) => i.id === id);
    const newIdx = idx + delta;
    if (idx < 0 || newIdx < 0 || newIdx >= images.length) return;
    const reordered = [...images];
    const [item] = reordered.splice(idx, 1);
    reordered.splice(newIdx, 0, item);
    setImages(reordered);
    try {
      await questionsAPI.reorderImage(id, newIdx);
    } catch (e: any) {
      setError('Failed to reorder image: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
    }
  }

  async function save(force = false) {
    setSaving(true);
    setError(null);
    setConflict(null);
    try {
      // Bug 2026-07-28: scrub bare `/media/fixtures/images/...` URLs
      // from every text field before sending. The legacy form of
      // these URLs is unreachable in production (Django refuses to
      // serve `/media/` when DEBUG=False) and the frontend's
      // resolver only upgrades bare URLs to `[[img:N]]` when an
      // attached QuestionImage row exists. If the admin pastes a
      // bare URL into the textarea by mistake, we instead:
      //   - replace it with the canonical `[[img:N]]` token if a
      //     row already exists for this question+basename, OR
      //   - replace it with a visible "[image unavailable: …]"
      //     marker so the student doesn't see a broken-image icon
      //     with no explanation.
      const cleanedForm: typeof form = { ...form };
      const fields = [
        'question_text', 'option_a', 'option_b', 'option_c',
        'option_d', 'explanation', 'mnemonic', 'concept_explanation',
      ] as const;
      for (const k of fields) {
        const v = (cleanedForm as any)[k];
        if (typeof v !== 'string') continue;
        (cleanedForm as any)[k] = v.replace(
          /\/media\/fixtures\/images\/([^/\s)\]]+)\/([^\s)\]]+)/g,
          (_match: string, exam: string, relPath: string) => {
              const base = relPath.split('/').pop() || relPath;
              const match = images.find(
                (img) => {
                    const f = (img.file || img.url || '').toString();
                    return f.split('/').pop()?.toLowerCase() === base.toLowerCase();
                },
              );
              if (match) return `[[img:${match.id}]]`;
              return `[image unavailable: ${base}]`;
          },
        );
      }
      const payload = { ...cleanedForm, admin_edited: true };
      // Only send If-Match when we have a real updated_at. List-serialised rows
      // don't include updated_at, so updatedAt may be '' on first edit — in that
      // case skip the optimistic lock and let the server accept the save.
      const opts = force || !updatedAt ? undefined : { ifMatch: updatedAt };
      const res = await questionsAPI.update(question.id, payload, opts);
      setUpdatedAt(res.data.updated_at ?? updatedAt);
      onSaved(res.data);
    } catch (e: any) {
      if (e?.response?.status === 409) {
        setConflict(e.response.data.current);
      } else {
        // Surface full server response so we can see field-level validation errors
        const detail = e?.response?.data?.detail;
        const data = e?.response?.data;
        const msg = detail
          ? `Save failed: ${detail}`
          : data && typeof data === 'object'
          ? `Save failed (${e?.response?.status ?? '?'}): ${JSON.stringify(data).slice(0, 400)}`
          : `Save failed: ${e?.message ?? 'unknown error'}`;
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  }

  function reloadFromConflict() {
    if (!conflict) return;
    setForm({
      question_text: conflict.question_text ?? '',
      option_a: conflict.option_a ?? '',
      option_b: conflict.option_b ?? '',
      option_c: conflict.option_c ?? '',
      option_d: conflict.option_d ?? '',
      correct_answer: conflict.correct_answer ?? 'A',
      explanation: conflict.explanation ?? '',
      mnemonic: conflict.mnemonic ?? '',
      concept_explanation: conflict.concept_explanation ?? '',
      difficulty: conflict.difficulty ?? 'medium',
      topic: conflict.topic ?? null,
      needs_review: !!conflict.needs_review,
      is_dropped: !!conflict.is_dropped,
      is_controversial: !!conflict.is_controversial,
    });
    setUpdatedAt(conflict.updated_at);
    setConflict(null);
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white text-gray-900 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-gray-900">Edit Question #{question.id}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800">×</button>
        </div>

        {error && <div className="bg-red-50 text-red-700 p-3 rounded">{error}</div>}
        {conflict && (
          <div className="bg-amber-50 border border-amber-300 p-3 rounded space-y-2">
            <p className="font-semibold">This question was edited by another user.</p>
            <button onClick={reloadFromConflict} className="bg-amber-200 px-3 py-1 rounded">Reload current values</button>
            <button onClick={() => save(true)} className="bg-amber-600 text-white px-3 py-1 rounded ml-2">Overwrite with my changes</button>
          </div>
        )}

        <label className="block">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900">Question Text</span>
            <div className="flex items-center gap-2">
              {renderInsertImageButton('question_text')}
            </div>
          </div>
          <div className="mt-1">{renderMarkdownToolbar('question_text')}</div>
          <textarea
            ref={(el) => { fieldRefs.current['question_text'] = el; }}
            className="w-full border border-gray-300 bg-white text-gray-900 placeholder-gray-400 p-2 rounded mt-1 font-mono text-sm"
            rows={6}
            value={form.question_text}
            onChange={(e) => setForm({ ...form, question_text: e.target.value })}
          />
          {renderInlinePreview(form.question_text)}
        </label>

        <details className="border border-gray-300 rounded p-2" open>
          <summary className="cursor-pointer text-sm font-medium text-gray-900">Preview (rendered)</summary>
          <div className="prose max-w-none mt-2 text-gray-900" dangerouslySetInnerHTML={{ __html: previewHtml }} />
        </details>

        <div className="grid grid-cols-2 gap-3">
          {(['option_a', 'option_b', 'option_c', 'option_d'] as const).map((k) => (
            <label key={k} className="block">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium uppercase text-gray-900">{k.replace('_', ' ')}</span>
                {renderInsertImageButton(k)}
              </div>
              <textarea
                ref={(el) => { fieldRefs.current[k] = el; }}
                className="w-full border border-gray-300 bg-white text-gray-900 placeholder-gray-400 p-2 rounded mt-1 text-sm"
                rows={2}
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
              {renderInlinePreview(form[k])}
            </label>
          ))}
        </div>

        <label className="block">
          <span className="text-sm font-medium text-gray-900">Correct Answer</span>
          <select
            className="border border-gray-300 bg-white text-gray-900 p-2 rounded ml-3"
            value={form.correct_answer}
            onChange={(e) => setForm({ ...form, correct_answer: e.target.value })}
          >
            {['A', 'B', 'C', 'D'].map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>

        <label className="block">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900">Explanation</span>
            {renderInsertImageButton('explanation')}
          </div>
          <div className="mt-1">{renderMarkdownToolbar('explanation')}</div>
          <textarea
            ref={(el) => { fieldRefs.current['explanation'] = el; }}
            className="w-full border border-gray-300 bg-white text-gray-900 placeholder-gray-400 p-2 rounded mt-1 text-sm"
            rows={4}
            value={form.explanation}
            onChange={(e) => setForm({ ...form, explanation: e.target.value })}
          />
          {renderInlinePreview(form.explanation)}
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-900">Mnemonic</span>
              {renderInsertImageButton('mnemonic')}
            </div>
            <div className="mt-1">{renderMarkdownToolbar('mnemonic')}</div>
            <textarea
              ref={(el) => { fieldRefs.current['mnemonic'] = el; }}
              className="w-full border border-gray-300 bg-white text-gray-900 placeholder-gray-400 p-2 rounded mt-1 text-sm"
              rows={2}
              value={form.mnemonic}
              onChange={(e) => setForm({ ...form, mnemonic: e.target.value })}
            />
            {renderInlinePreview(form.mnemonic)}
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-900">Difficulty</span>
            <select
              className="border border-gray-300 bg-white text-gray-900 p-2 rounded mt-1 w-full"
              value={form.difficulty}
              onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>
        </div>

        <label className="block">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900">Concept Explanation</span>
            {renderInsertImageButton('concept_explanation')}
          </div>
          <div className="mt-1">{renderMarkdownToolbar('concept_explanation')}</div>
          <textarea
            ref={(el) => { fieldRefs.current['concept_explanation'] = el; }}
            className="w-full border border-gray-300 bg-white text-gray-900 placeholder-gray-400 p-2 rounded mt-1 text-sm"
            rows={3}
            value={form.concept_explanation}
            onChange={(e) => setForm({ ...form, concept_explanation: e.target.value })}
          />
          {renderInlinePreview(form.concept_explanation)}
        </label>

        <div className="flex gap-4 text-sm text-gray-900">
          {(['needs_review', 'is_dropped', 'is_controversial'] as const).map((k) => (
            <label key={k} className="flex items-center gap-2 text-gray-900">
              <input
                type="checkbox"
                checked={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.checked })}
              />
              {k.replace(/_/g, ' ')}
            </label>
          ))}
        </div>

        <div className="border-t border-gray-200 pt-3">
          <p className="text-sm font-medium mb-2 text-gray-900">Images attached ({images.length})</p>
          <div className="grid grid-cols-3 gap-2">
            {images.map((img, idx) => {
              const src = imageSrc(img);
              return (
                <div key={img.id} className="border border-gray-300 rounded p-2 text-xs text-gray-900 space-y-1">
                  <div className="relative w-full aspect-square bg-gray-50 rounded overflow-hidden flex items-center justify-center">
                    {src ? (
                      <img
                        src={src}
                        alt={img.caption || `image #${img.id}`}
                        className="w-full h-full object-cover"
                        loading="lazy"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).style.display = 'none';
                          const fallback = (e.currentTarget as HTMLImageElement).nextElementSibling as HTMLElement | null;
                          if (fallback) fallback.style.display = 'flex';
                        }}
                      />
                    ) : null}
                    <div
                      className="absolute inset-0 hidden flex-col items-center justify-center text-center text-[10px] text-gray-500 p-1"
                      style={src ? { display: 'none' } : { display: 'flex' }}
                    >
                      <span className="font-mono">#{img.id}</span>
                      <span>{src ? 'broken link' : 'no url yet'}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono">#{img.id}</span>
                    <span className="text-gray-500 truncate max-w-[8rem]" title={img.mime || ''}>{img.mime}</span>
                  </div>
                  {img.caption && (
                    <div className="truncate text-gray-700" title={img.caption}>{img.caption}</div>
                  )}
                  <div className="flex gap-1 mt-1">
                    <button onClick={() => moveImage(img.id, -1)} disabled={idx === 0} className="px-1 text-gray-900" title="Move up">↑</button>
                    <button onClick={() => moveImage(img.id, 1)} disabled={idx === images.length - 1} className="px-1 text-gray-900" title="Move down">↓</button>
                    {src && (
                      <a href={src} target="_blank" rel="noreferrer" className="px-1 text-indigo-600" title="Open in new tab">↗</a>
                    )}
                    <button onClick={() => deleteImage(img.id)} className="px-1 text-red-500 ml-auto" title="Delete">×</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
          <button onClick={onClose} className="px-4 py-2 border border-gray-300 rounded text-gray-900 bg-white">Cancel</button>
          <button onClick={() => save(false)} disabled={saving} className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
