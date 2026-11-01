'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { questionsAPI } from '@/lib/api';
import { resolveImageTokens, type QuestionImageLike } from '@/lib/imageTokens';
import { Sparkles } from 'lucide-react';
import { buildQuestionEditPayload, isValidAnswerLetter, unpersistedEditFields } from '../_lib/adminHelpers';

interface QuestionEditModalProps {
  question: any;
  images: QuestionImageLike[];
  onClose: () => void;
  onSaved: (updated: any) => void;
  onSaveAndNext?: (updated: any) => void;
}

type EditForm = ReturnType<typeof formFromQuestion>;

// Text fields scrubbed of legacy bare /media/fixtures/images/... URLs on save.
const SCRUBBED_TEXT_FIELDS = [
  'question_text', 'option_a', 'option_b', 'option_c',
  'option_d', 'explanation', 'mnemonic', 'concept_explanation',
  'reference_text', 'shortcut_tip', 'why_correct',
  'why_wrong_a', 'why_wrong_b', 'why_wrong_c', 'why_wrong_d',
] as const;

// Editable fields from a list row, detail payload or 409 `current` body.
function formFromQuestion(q: any) {
  return {
    question_text: q.question_text ?? '',
    option_a: q.option_a ?? '',
    option_b: q.option_b ?? '',
    option_c: q.option_c ?? '',
    option_d: q.option_d ?? '',
    // No silent "A": an unset answer stays unset until the admin picks one
    // (it used to default to A, which was then saved and fed to the AI).
    correct_answer: isValidAnswerLetter(q.correct_answer) ? String(q.correct_answer).trim().toUpperCase() : '',
    explanation: q.explanation ?? '',
    mnemonic: q.mnemonic ?? '',
    concept_explanation: q.concept_explanation ?? '',
    difficulty: q.difficulty ?? 'medium',
    topic: q.topic ?? null,
    needs_review: !!q.needs_review,
    is_dropped: !!q.is_dropped,
    is_controversial: !!q.is_controversial,
    // AI-generated explanation fields (all editable by admin)
    concept_keywords: Array.isArray(q.concept_keywords) ? q.concept_keywords.join(', ') : (q.concept_keywords ?? ''),
    book_name: q.book_name ?? '',
    chapter: q.chapter ?? '',
    page_number: q.page_number ?? '',
    reference_text: q.reference_text ?? '',
    shortcut_tip: q.shortcut_tip ?? '',
    why_correct: q.why_correct ?? '',
    why_wrong_a: q.why_wrong_a ?? '',
    why_wrong_b: q.why_wrong_b ?? '',
    why_wrong_c: q.why_wrong_c ?? '',
    why_wrong_d: q.why_wrong_d ?? '',
  };
}

export default function QuestionEditModal({ question, images: initialImages, onClose, onSaved, onSaveAndNext }: QuestionEditModalProps) {
  // The parent renders this with key={question.id}, so every question gets a
  // fresh instance (state used to leak from one question into the next).
  const [form, setForm] = useState<EditForm>(() => formFromQuestion(question));
  // Server-side values the form was loaded from (or last saved to). Used to
  // send is_controversial only when toggled and to detect edits the server
  // did not store.
  const baselineRef = useRef<EditForm>(form);
  const [images, setImages] = useState<QuestionImageLike[]>(initialImages);
  const [updatedAt, setUpdatedAt] = useState<string>(question.updated_at ?? '');
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<any | null>(null);
  const [uploadingField, setUploadingField] = useState<string | null>(null);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiSuccess, setAiSuccess] = useState<string | null>(null);
  const [aiGeneratedFields, setAiGeneratedFields] = useState<string[]>([]);
  const fieldRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const formRef = useRef(form);
  formRef.current = form;

  // Latest save handlers for the keyboard shortcuts below. The listener is
  // registered once; it used to capture the first render's save()/form, so
  // Ctrl+S saved stale values and dropped the edits made since.
  const saveRef = useRef<(force?: boolean) => Promise<boolean>>(async () => false);
  const saveAndNextRef = useRef<() => Promise<void>>(async () => {});
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const hasSaveAndNextRef = useRef(Boolean(onSaveAndNext));
  hasSaveAndNextRef.current = Boolean(onSaveAndNext);

  // Keyboard shortcuts for fast sequential processing:
  //   Ctrl/Cmd + S  → Save
  //   Ctrl/Cmd + →  → Save and Next question
  //   Ctrl/Cmd + ←  → Save, then Previous question (only if the save worked)
  //   Escape        → Close (only when not editing a text field)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const active = document.activeElement;
      const isEditing = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || (active as HTMLElement).isContentEditable);

      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        void saveRef.current(false);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'ArrowRight') {
        e.preventDefault();
        if (hasSaveAndNextRef.current) void saveAndNextRef.current();
        else void saveRef.current(false);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'ArrowLeft') {
        e.preventDefault();
        void saveRef.current(false).then((ok) => {
          if (ok) window.dispatchEvent(new CustomEvent('admin-qeditor:prev'));
        });
        return;
      }
      if (e.key === 'Escape' && !isEditing) {
        e.preventDefault();
        onCloseRef.current();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

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

  // When the parent opens a new question (Save & Next, prev/next nav),
  // re-fetch the full detail payload. The list endpoint may strip
  // explanation fields depending on auth context / serializer, so
  // without this step the admin sees empty textareas for questions
  // that were AI-explained from another session.
  const [loadingDetail, setLoadingDetail] = useState(false);
  useEffect(() => {
    let cancelled = false;
    async function loadFullQuestion() {
      if (!question?.id) return;
      // If the prop already has an explanation, the list serializer
      // probably included it — skip the extra fetch.
      if (question.explanation || question.concept_explanation || question.mnemonic) {
        setUpdatedAt(question.updated_at ?? '');
        return;
      }
      setLoadingDetail(true);
      setError(null);
      try {
        const detail = await questionsAPI.get(question.id);
        if (cancelled) return;
        // Detail values win; the list row fills what the detail serializer
        // lacks (why_correct / why_wrong_*), which used to reset to empty
        // here and could then be saved over the real values.
        const next = formFromQuestion({ ...question, ...(detail.data || {}) });
        setForm(next);
        baselineRef.current = next;
        setUpdatedAt(detail.data?.updated_at ?? '');
      } catch (e: any) {
        if (cancelled) return;
        console.warn('Failed to fetch full question detail, using prop data:', e);
        setError(e?.response?.data?.detail || 'Could not load full question data. Using cached data.');
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    }
    loadFullQuestion();
    return () => { cancelled = true; };
  }, [question.id]);

  // Rendered preview of the stem, from a debounced copy of the text.
  // resolveImageTokens() keys its (bounded) cache on a hash of the text and
  // images itself, so the key below is only a namespace: the old key (id +
  // image ids) ignored the text and kept showing the first-rendered stem,
  // and putting the whole stem in the key grew the cache on every pause.
  const [previewSource, setPreviewSource] = useState<string>(form.question_text);
  useEffect(() => {
    const timer = setTimeout(() => setPreviewSource(form.question_text), 250);
    return () => clearTimeout(timer);
  }, [form.question_text]);
  const previewHtml = useMemo(
    () => resolveImageTokens(previewSource, images, `qe:${question.id}`),
    [previewSource, images, question.id],
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
            className="block w-20 h-20 border border-gray-300 dark:border-slate-700 rounded overflow-hidden bg-gray-50 dark:bg-slate-800"
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
      'inline-flex items-center justify-center min-w-7 h-7 px-2 rounded border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-800 hover:border-gray-400 dark:hover:border-slate-500 text-xs font-semibold transition';
    return (
      <div className="flex flex-wrap gap-1 items-center" role="toolbar" aria-label={`Formatting toolbar for ${fieldKey}`}>
        <button type="button" title="Bold (**)" onClick={() => insertAtCursor(fieldKey, '', { open: '**', close: '**', placeholder: 'bold' })} className={btnBase}>B</button>
        <button type="button" title="Italic (*)" onClick={() => insertAtCursor(fieldKey, '', { open: '*', close: '*', placeholder: 'italic' })} className={btnBase}><span className="italic">I</span></button>
        <span className="w-px h-5 bg-gray-200 dark:bg-slate-700 mx-1" aria-hidden />
        <button type="button" title="Heading 1 (#)" onClick={() => insertLineStart(fieldKey, '# ')} className={btnBase}>H1</button>
        <button type="button" title="Heading 2 (##)" onClick={() => insertLineStart(fieldKey, '## ')} className={btnBase}>H2</button>
        <button type="button" title="Bullet list (-)" onClick={() => insertLineStart(fieldKey, '- ')} className={btnBase}>•</button>
        <button type="button" title="Quote (>)" onClick={() => insertLineStart(fieldKey, '> ')} className={btnBase}>&ldquo;</button>
        <span className="w-px h-5 bg-gray-200 dark:bg-slate-700 mx-1" aria-hidden />
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
        // Send `role='explanation'` when the upload is triggered from the
        // explanation / concept_explanation / mnemonic editor so the
        // backend records the row with role='explanation'. The question
        // stem pane then filters these out and stops showing the figure
        // before the student attempts the question. The explanation /
        // mnemonic text itself still renders the figure inline via the
        // `[[img:N]]` token we insert below.
        const role: 'primary' | 'option' | 'illustration' | 'explanation' =
          fieldKey === 'explanation' ||
          fieldKey === 'concept_explanation' ||
          fieldKey === 'mnemonic'
            ? 'explanation'
            : 'illustration';
        const res = await questionsAPI.uploadImage({ questionId: question.id, file, role });
        const img = res.data as QuestionImageLike;
        const newImages = [...images, img];
        setImages(newImages);
        const token = `[[img:${img.id}]]`;
        // Functional updates: the upload is async, and spreading the form
        // captured before it dropped anything typed while it ran.
        if (ref) {
          const start = ref.selectionStart ?? ref.value.length;
          const end = ref.selectionEnd ?? ref.value.length;
          setForm((prev) => {
            const currentValue = (prev as any)[fieldKey] ?? '';
            return { ...prev, [fieldKey]: currentValue.slice(0, start) + token + currentValue.slice(end) };
          });
        } else {
          // No ref available — append to the end of the field.
          setForm((prev) => ({ ...prev, [fieldKey]: ((prev as any)[fieldKey] ?? '') + token }));
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
      setImages((prev) => prev.filter((i) => i.id !== id));
      const tokenRe = new RegExp(`\\[\\[img:${id}\\]\\]`, 'g');
      setForm((prev) => {
        const updated: any = { ...prev };
        for (const k of fieldsWithImages.map((f) => f.key)) {
          const v = (prev as any)[k];
          if (typeof v === 'string') updated[k] = v.replace(tokenRe, '');
        }
        return updated;
      });
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
  function scrubMediaUrls(source: EditForm): EditForm {
    const cleanedForm: EditForm = { ...source };
    for (const k of SCRUBBED_TEXT_FIELDS) {
      const v = (cleanedForm as any)[k];
      if (typeof v !== 'string') continue;
      (cleanedForm as any)[k] = v.replace(
        /\/media\/fixtures\/images\/([^/\s)\]]+)\/([^\s)\]]+)/g,
        (_match: string, _exam: string, relPath: string) => {
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
    return cleanedForm;
  }

  // PATCH the question (Save and Save & Next share this). Resolves to the
  // saved row plus any edited fields the server did not store, or null when
  // the save failed (the error / conflict banner is shown).
  async function persist(force: boolean): Promise<{ saved: any; dropped: string[] } | null> {
    // No save while a save is in flight or before the full question has
    // loaded (the keyboard shortcuts bypass the disabled buttons).
    if (savingRef.current || loadingDetail) return null;
    savingRef.current = true;
    setSaving(true);
    setError(null);
    setConflict(null);
    try {
      const baseline = baselineRef.current;
      // concept_keywords goes out as a list, correct_answer only when it is a
      // real letter, is_controversial only when toggled (buildQuestionEditPayload).
      const payload = buildQuestionEditPayload(scrubMediaUrls(form), baseline);
      // Only send If-Match when we have a real updated_at. List-serialised rows
      // don't include updated_at, so updatedAt may be '' on first edit — in that
      // case skip the optimistic lock and let the server accept the save.
      const opts = force || !updatedAt ? undefined : { ifMatch: updatedAt };
      const res = await questionsAPI.update(question.id, payload, opts);
      setUpdatedAt(res.data.updated_at ?? updatedAt);
      // Edits the PATCH silently ignored (the field is absent from the
      // response): keep them marked as unsaved and tell the admin.
      const dropped = unpersistedEditFields(payload, baseline, res.data);
      const nextBaseline: any = { ...form };
      for (const field of dropped) nextBaseline[field] = (baseline as any)[field];
      baselineRef.current = nextBaseline;
      if (dropped.length > 0) {
        setError(
          `Saved, but the server did not store: ${dropped.join(', ')}. ` +
          'Those edits are only in this form and will be lost if you leave it.',
        );
      }
      onSaved(res.data);
      return { saved: res.data, dropped };
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
      return null;
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  async function save(force = false): Promise<boolean> {
    return (await persist(force)) !== null;
  }

  async function saveAndNext(): Promise<void> {
    const result = await persist(false);
    // Stay on this question if the save failed or some edits were not stored.
    if (result && result.dropped.length === 0 && onSaveAndNext) onSaveAndNext(result.saved);
  }

  saveRef.current = save;
  saveAndNextRef.current = saveAndNext;

  function reloadFromConflict() {
    if (!conflict) return;
    // The 409 body is the detail serializer; the list row fills the gaps.
    const next = formFromQuestion({ ...question, ...conflict });
    setForm(next);
    baselineRef.current = next;
    setUpdatedAt(conflict.updated_at);
    setConflict(null);
  }

  async function generateAIExplanation() {
    // The AI is told this letter is correct (and it is stored as the answer),
    // so it must be an explicit choice.
    if (!isValidAnswerLetter(form.correct_answer)) {
      setAiError('Select the correct answer first: the explanation is written for that answer.');
      return;
    }
    const correctAnswer = form.correct_answer;
    setAiGenerating(true);
    setAiError(null);
    setAiSuccess(null);
    setAiGeneratedFields([]);
    const requestGeneration = (regenerate: boolean) => questionsAPI.generateExplanation(question.id, {
      correct_answer: correctAnswer,
      regenerate_if_exists: regenerate,
      update_correct_answer: true,
    });
    try {
      let res;
      try {
        res = await requestGeneration(false);
      } catch (e: any) {
        // An existing explanation comes back as HTTP 409, which axios rejects;
        // the old `res.status === 409` check therefore never ran and the
        // overwrite confirmation was unreachable.
        if (e?.response?.status !== 409) throw e;
        if (!window.confirm('This question already has an explanation. Overwrite with AI-generated content?')) {
          return;
        }
        res = await requestGeneration(true);
      }
      // The endpoint saves the AI output and marks a previously unverified
      // question "Verified by Admin" (a student-facing badge). Unreviewed AI
      // content must not carry it, so restore the unverified state, and say
      // so when that fails instead of claiming "not marked verified".
      let stillVerified = false;
      if (!question.is_verified_by_admin && res?.data?.question?.is_verified_by_admin) {
        try {
          await questionsAPI.unverify(question.id);
        } catch {
          stillVerified = true;
        }
      }
      applyGeneratedFields(res?.data, correctAnswer, stillVerified);
      // The endpoint saved the question, so updated_at moved: refresh it or
      // the next Save is rejected as "edited by another user".
      try {
        const detail = await questionsAPI.get(question.id);
        setUpdatedAt(detail.data?.updated_at ?? '');
      } catch {
        setUpdatedAt('');
      }
    } catch (e: any) {
      setAiError(e?.response?.data?.detail || e?.response?.data?.error || e?.message || 'AI generation failed.');
    } finally {
      setAiGenerating(false);
    }
  }

  function applyGeneratedFields(data: any, correctAnswer: string, stillVerified = false) {
    const generated = data?.generated_fields || {};
    // formRef: generation takes 15-30 s; keep edits made meanwhile.
    const updated: any = { ...formRef.current };
    const nextBaseline: any = { ...baselineRef.current, correct_answer: correctAnswer };
    const applied: string[] = [];
    for (const [key, value] of Object.entries(generated)) {
      if (key in updated) {
        const formValue = key === 'concept_keywords' && Array.isArray(value) ? value.join(', ') : value;
        updated[key] = formValue;
        // The endpoint already stored these values.
        nextBaseline[key] = formValue;
        applied.push(key);
      }
    }
    baselineRef.current = nextBaseline;
    setForm(updated);
    setAiGeneratedFields(applied);
    if (stillVerified) {
      setAiSuccess(`Generated ${applied.length} fields. They are already saved to the question; review them and Save your edits.`);
      setAiError('Still marked "Verified by Admin": removing the mark failed. Unverify it in Admin > Question Bank.');
      return;
    }
    setAiSuccess(
      question.is_verified_by_admin
        ? `Generated ${applied.length} fields. They are already saved to the question, which keeps its earlier "verified" mark; review them and Save your edits.`
        : `Generated ${applied.length} fields. They are already saved to the question (not marked verified); review them and Save your edits.`,
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100">
            Edit Question #{question.id}
            {loadingDetail && (
              <span className="ml-3 text-xs font-normal text-gray-500 dark:text-slate-400 animate-pulse">Loading full question…</span>
            )}
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 dark:text-slate-400 dark:hover:text-slate-100">×</button>
        </div>

        {error && <div className="bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-200 p-3 rounded">{error}</div>}
        {conflict && (
          <div className="bg-amber-50 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 p-3 rounded space-y-2">
            <p className="font-semibold text-gray-900 dark:text-slate-100">This question was edited by another user.</p>
            <button onClick={reloadFromConflict} className="bg-amber-200 dark:bg-amber-700 text-gray-900 dark:text-slate-100 px-3 py-1 rounded">Reload current values</button>
            <button onClick={() => save(true)} className="bg-amber-600 text-white px-3 py-1 rounded ml-2">Overwrite with my changes</button>
          </div>
        )}

        <label className="block">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Question Text</span>
            <div className="flex items-center gap-2">
              {renderInsertImageButton('question_text')}
            </div>
          </div>
          <div className="mt-1">{renderMarkdownToolbar('question_text')}</div>
          <textarea
            ref={(el) => { fieldRefs.current['question_text'] = el; }}
            className="w-full border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder-gray-400 dark:placeholder-slate-500 p-2 rounded mt-1 font-mono text-sm"
            rows={6}
            value={form.question_text}
            onChange={(e) => setForm({ ...form, question_text: e.target.value })}
          />
          {renderInlinePreview(form.question_text)}
        </label>

        <details className="border border-gray-300 dark:border-slate-700 rounded p-2" open>
          <summary className="cursor-pointer text-sm font-medium text-gray-900 dark:text-slate-100">Preview (rendered)</summary>
          <div className="prose max-w-none mt-2 text-gray-900 dark:text-slate-100 dark:prose-invert" dangerouslySetInnerHTML={{ __html: previewHtml }} />
        </details>

        <div className="grid grid-cols-2 gap-3">
          {(['option_a', 'option_b', 'option_c', 'option_d'] as const).map((k) => (
            <label key={k} className="block">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium uppercase text-gray-900 dark:text-slate-100">{k.replace('_', ' ')}</span>
                {renderInsertImageButton(k)}
              </div>
              <textarea
                ref={(el) => { fieldRefs.current[k] = el; }}
                className="w-full border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder-gray-400 dark:placeholder-slate-500 p-2 rounded mt-1 text-sm"
                rows={2}
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
              {renderInlinePreview(form[k])}
            </label>
          ))}
        </div>

        <label className="block">
          <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Correct Answer</span>
          <select
            className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-2 rounded ml-3"
            value={form.correct_answer}
            onChange={(e) => setForm({ ...form, correct_answer: e.target.value })}
          >
            {!isValidAnswerLetter(form.correct_answer) && <option value="">— Not set —</option>}
            {['A', 'B', 'C', 'D'].map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>

        <label className="block">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Explanation</span>
            {renderInsertImageButton('explanation')}
          </div>
          <div className="mt-1">{renderMarkdownToolbar('explanation')}</div>
          <textarea
            ref={(el) => { fieldRefs.current['explanation'] = el; }}
            className="w-full border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder-gray-400 dark:placeholder-slate-500 p-2 rounded mt-1 text-sm"
            rows={4}
            value={form.explanation}
            onChange={(e) => setForm({ ...form, explanation: e.target.value })}
          />
          {renderInlinePreview(form.explanation)}
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Mnemonic</span>
              {renderInsertImageButton('mnemonic')}
            </div>
            <div className="mt-1">{renderMarkdownToolbar('mnemonic')}</div>
            <textarea
              ref={(el) => { fieldRefs.current['mnemonic'] = el; }}
              className="w-full border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder-gray-400 dark:placeholder-slate-500 p-2 rounded mt-1 text-sm"
              rows={2}
              value={form.mnemonic}
              onChange={(e) => setForm({ ...form, mnemonic: e.target.value })}
            />
            {renderInlinePreview(form.mnemonic)}
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Difficulty</span>
            <select
              className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-2 rounded mt-1 w-full"
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
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Concept Explanation</span>
            {renderInsertImageButton('concept_explanation')}
          </div>
          <div className="mt-1">{renderMarkdownToolbar('concept_explanation')}</div>
          <textarea
            ref={(el) => { fieldRefs.current['concept_explanation'] = el; }}
            className="w-full border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder-gray-400 dark:placeholder-slate-500 p-2 rounded mt-1 text-sm"
            rows={3}
            value={form.concept_explanation}
            onChange={(e) => setForm({ ...form, concept_explanation: e.target.value })}
          />
          {renderInlinePreview(form.concept_explanation)}
        </label>

        {/* Why correct + why wrong grid */}
        <div className="border-t border-gray-200 dark:border-slate-700 pt-3 space-y-3">
          <p className="text-sm font-semibold text-gray-900 dark:text-slate-100">AI Explanation Details</p>
          <label className="block">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Why Correct Answer is Right</span>
            <textarea
              ref={(el) => { fieldRefs.current['why_correct'] = el; }}
              className={"w-full border rounded p-2 mt-1 text-sm " + (aiGeneratedFields.includes('why_correct') ? 'ring-2 ring-violet-400 bg-violet-50 dark:bg-violet-900/20' : 'border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100')}
              rows={2}
              value={form.why_correct}
              onChange={(e) => setForm({ ...form, why_correct: e.target.value })}
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            {(['a','b','c','d'] as const).map((opt) => {
              const fieldKey = `why_wrong_${opt}` as keyof typeof form;
              const fieldLabel = `Why Option ${opt.toUpperCase()} is Wrong`;
              return (
                <label key={opt} className="block">
                  <span className="text-sm font-medium text-gray-900 dark:text-slate-100">
                    {fieldLabel}
                  </span>
                  <textarea
                    ref={(el) => { fieldRefs.current[fieldKey] = el; }}
                    className={"w-full border rounded p-2 mt-1 text-sm " + (aiGeneratedFields.includes(fieldKey) ? 'ring-2 ring-violet-400 bg-violet-50 dark:bg-violet-900/20' : 'border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100')}
                    rows={2}
                    value={form[fieldKey] as string}
                    onChange={(e) => setForm({ ...form, [fieldKey]: e.target.value })}
                  />
                </label>
              );
            })}
          </div>
        </div>

        {/* Textbook reference fields */}
        <div className="border-t border-gray-200 dark:border-slate-700 pt-3 grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Book Name</span>
            <input
              className={"w-full border rounded p-2 mt-1 text-sm " + (aiGeneratedFields.includes('book_name') ? 'ring-2 ring-violet-400 bg-violet-50 dark:bg-violet-900/20' : 'border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100')}
              value={form.book_name}
              onChange={(e) => setForm({ ...form, book_name: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Chapter</span>
            <input
              className={"w-full border rounded p-2 mt-1 text-sm " + (aiGeneratedFields.includes('chapter') ? 'ring-2 ring-violet-400 bg-violet-50 dark:bg-violet-900/20' : 'border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100')}
              value={form.chapter}
              onChange={(e) => setForm({ ...form, chapter: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Page Number</span>
            <input
              className="w-full border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded p-2 mt-1 text-sm"
              value={form.page_number}
              onChange={(e) => setForm({ ...form, page_number: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Reference Text</span>
            <textarea
              ref={(el) => { fieldRefs.current['reference_text'] = el; }}
              className={"w-full border rounded p-2 mt-1 text-sm " + (aiGeneratedFields.includes('reference_text') ? 'ring-2 ring-violet-400 bg-violet-50 dark:bg-violet-900/20' : 'border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100')}
              rows={2}
              value={form.reference_text}
              onChange={(e) => setForm({ ...form, reference_text: e.target.value })}
            />
          </label>
        </div>

        <label className="block">
          <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Shortcut Tip (exam-solving strategy)</span>
          <textarea
            ref={(el) => { fieldRefs.current['shortcut_tip'] = el; }}
            className={"w-full border rounded p-2 mt-1 text-sm " + (aiGeneratedFields.includes('shortcut_tip') ? 'ring-2 ring-violet-400 bg-violet-50 dark:bg-violet-900/20' : 'border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100')}
            rows={2}
            value={form.shortcut_tip}
            onChange={(e) => setForm({ ...form, shortcut_tip: e.target.value })}
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-gray-900 dark:text-slate-100">Concept Keywords (comma-separated)</span>
          <input
            className={"w-full border rounded p-2 mt-1 text-sm " + (aiGeneratedFields.includes('concept_keywords') ? 'ring-2 ring-violet-400 bg-violet-50 dark:bg-violet-900/20' : 'border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100')}
            value={form.concept_keywords}
            onChange={(e) => setForm({ ...form, concept_keywords: e.target.value })}
            placeholder="e.g. hypertension, renal artery stenosis, ACE inhibitor"
          />
        </label>

        <div className="flex gap-4 text-sm text-gray-900 dark:text-slate-100">
          {(['needs_review', 'is_dropped', 'is_controversial'] as const).map((k) => (
            <label key={k} className="flex items-center gap-2 text-gray-900 dark:text-slate-100">
              <input
                type="checkbox"
                checked={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.checked })}
              />
              {k.replace(/_/g, ' ')}
            </label>
          ))}
        </div>

        <div className="border-t border-gray-200 dark:border-slate-700 pt-3">
          <p className="text-sm font-medium mb-2 text-gray-900 dark:text-slate-100">Images attached ({images.length})</p>
          <div className="grid grid-cols-3 gap-2">
            {images.map((img, idx) => {
              const src = imageSrc(img);
              return (
                <div key={img.id} className="border border-gray-300 dark:border-slate-700 rounded p-2 text-xs text-gray-900 dark:text-slate-100 space-y-1">
                  <div className="relative w-full aspect-square bg-gray-50 dark:bg-slate-800 rounded overflow-hidden flex items-center justify-center">
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
                      className="absolute inset-0 hidden flex-col items-center justify-center text-center text-[10px] text-gray-500 dark:text-slate-400 p-1"
                      style={src ? { display: 'none' } : { display: 'flex' }}
                    >
                      <span className="font-mono">#{img.id}</span>
                      <span>{src ? 'broken link' : 'no url yet'}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono">#{img.id}</span>
                    <span className="text-gray-500 dark:text-slate-400 truncate max-w-32" title={img.mime || ''}>{img.mime}</span>
                  </div>
                  {img.caption && (
                    <div className="truncate text-gray-700 dark:text-slate-300" title={img.caption}>{img.caption}</div>
                  )}
                  <div className="flex gap-1 mt-1">
                    <button onClick={() => moveImage(img.id, -1)} disabled={idx === 0} className="px-1 text-gray-900 dark:text-slate-100" title="Move up">↑</button>
                    <button onClick={() => moveImage(img.id, 1)} disabled={idx === images.length - 1} className="px-1 text-gray-900 dark:text-slate-100" title="Move down">↓</button>
                    {src && (
                      <a href={src} target="_blank" rel="noreferrer" className="px-1 text-indigo-600 dark:text-indigo-400" title="Open in new tab">↗</a>
                    )}
                    <button onClick={() => deleteImage(img.id)} className="px-1 text-red-500 dark:text-red-400 ml-auto" title="Delete">×</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex justify-between gap-2 pt-3 border-t border-gray-200 dark:border-slate-700">
          <div className="flex gap-2 items-center">
            {aiSuccess && (
              <span className="text-xs text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-900/30 px-2 py-1 rounded">
                {aiSuccess}
              </span>
            )}
            {aiError && (
              <span className="text-xs text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 px-2 py-1 rounded max-w-md truncate" title={aiError}>
                {aiError}
              </span>
            )}
            {aiGeneratedFields.length > 0 && (
              <span className="text-xs text-emerald-600 dark:text-emerald-400">
                Populated: {aiGeneratedFields.join(', ')}
              </span>
            )}
            <button
              onClick={generateAIExplanation}
              disabled={aiGenerating || saving || loadingDetail}
              title="Use Medical AI to generate explanation based on the selected correct answer"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
              <Sparkles />
              {aiGenerating ? 'Generating…' : 'AI Generate Explanation'}
            </button>
            {aiGenerating && (
              <span className="text-xs text-gray-500 dark:text-slate-400 animate-pulse">This may take 15–30 seconds…</span>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 border border-gray-300 dark:border-slate-700 rounded text-gray-900 dark:text-slate-100 bg-white dark:bg-slate-900">Cancel</button>
            <button onClick={() => save(false)} disabled={saving || loadingDetail} className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50">
              {saving ? 'Saving…' : 'Save'}
            </button>
            {onSaveAndNext && (
              <button onClick={() => saveAndNext()} disabled={saving || aiGenerating || loadingDetail} className="bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50 flex items-center gap-1">
                Save &amp; Next <span className="text-xs opacity-75">&rarr;</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
