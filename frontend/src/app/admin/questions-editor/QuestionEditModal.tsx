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
  const questionTextRef = useRef<HTMLTextAreaElement>(null);
  const explanationRef = useRef<HTMLTextAreaElement>(null);

  const previewHtml = useMemo(
    () => resolveImageTokens(form.question_text, images, `${question.id}:${images.map((i) => i.id).join('|')}`),
    [form.question_text, images, question.id],
  );

  async function insertImage(target: 'question' | 'explanation') {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/webp,image/gif';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const res = await questionsAPI.uploadImage({ questionId: question.id, file });
        const img = res.data as QuestionImageLike;
        const newImages = [...images, img];
        setImages(newImages);
        const token = `[[img:${img.id}]]`;
        const ref = target === 'question' ? questionTextRef.current : explanationRef.current;
        if (ref) {
          const start = ref.selectionStart ?? ref.value.length;
          const end = ref.selectionEnd ?? ref.value.length;
          const fieldKey = target === 'question' ? 'question_text' : 'explanation';
          setForm({ ...form, [fieldKey]: ref.value.slice(0, start) + token + ref.value.slice(end) });
        }
      } catch (e: any) {
        setError('Failed to upload image: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
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
      setForm({
        ...form,
        question_text: form.question_text.replace(tokenRe, ''),
        explanation: form.explanation.replace(tokenRe, ''),
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

  async function save(force = false) {
    setSaving(true);
    setError(null);
    setConflict(null);
    try {
      const payload = { ...form, admin_edited: true };
      const opts = force ? undefined : { ifMatch: updatedAt };
      const res = await questionsAPI.update(question.id, payload, opts);
      setUpdatedAt(res.data.updated_at ?? updatedAt);
      onSaved(res.data);
    } catch (e: any) {
      if (e?.response?.status === 409) {
        setConflict(e.response.data.current);
      } else {
        setError('Save failed: ' + (e?.response?.data?.detail || e?.message || 'unknown'));
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
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold">Edit Question #{question.id}</h2>
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
          <span className="text-sm font-medium">Question Text</span>
          <textarea
            ref={questionTextRef}
            className="w-full border p-2 rounded mt-1 font-mono text-sm"
            rows={6}
            value={form.question_text}
            onChange={(e) => setForm({ ...form, question_text: e.target.value })}
          />
          <button onClick={() => insertImage('question')} className="mt-1 text-xs bg-emerald-50 text-emerald-700 px-2 py-1 rounded">
            + Insert image
          </button>
        </label>

        <details className="border rounded p-2">
          <summary className="cursor-pointer text-sm font-medium">Preview (rendered)</summary>
          <div className="prose max-w-none mt-2" dangerouslySetInnerHTML={{ __html: previewHtml }} />
        </details>

        <div className="grid grid-cols-2 gap-3">
          {(['option_a', 'option_b', 'option_c', 'option_d'] as const).map((k) => (
            <label key={k} className="block">
              <span className="text-sm font-medium uppercase">{k}</span>
              <textarea
                className="w-full border p-2 rounded mt-1 text-sm"
                rows={2}
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
            </label>
          ))}
        </div>

        <label className="block">
          <span className="text-sm font-medium">Correct Answer</span>
          <select
            className="border p-2 rounded ml-3"
            value={form.correct_answer}
            onChange={(e) => setForm({ ...form, correct_answer: e.target.value })}
          >
            {['A', 'B', 'C', 'D'].map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium">Explanation</span>
          <textarea
            ref={explanationRef}
            className="w-full border p-2 rounded mt-1 text-sm"
            rows={4}
            value={form.explanation}
            onChange={(e) => setForm({ ...form, explanation: e.target.value })}
          />
          <button onClick={() => insertImage('explanation')} className="mt-1 text-xs bg-emerald-50 text-emerald-700 px-2 py-1 rounded">
            + Insert image
          </button>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-sm font-medium">Mnemonic</span>
            <textarea
              className="w-full border p-2 rounded mt-1 text-sm"
              rows={2}
              value={form.mnemonic}
              onChange={(e) => setForm({ ...form, mnemonic: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">Difficulty</span>
            <select
              className="border p-2 rounded mt-1 w-full"
              value={form.difficulty}
              onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>
        </div>

        <div className="flex gap-4 text-sm">
          {(['needs_review', 'is_dropped', 'is_controversial'] as const).map((k) => (
            <label key={k} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.checked })}
              />
              {k.replace(/_/g, ' ')}
            </label>
          ))}
        </div>

        <div className="border-t pt-3">
          <p className="text-sm font-medium mb-2">Images attached ({images.length})</p>
          <div className="grid grid-cols-3 gap-2">
            {images.map((img, idx) => (
              <div key={img.id} className="border rounded p-2 text-xs">
                <div className="font-mono">#{img.id}</div>
                <div className="truncate">{img.caption || img.mime}</div>
                <div className="flex gap-1 mt-1">
                  <button onClick={() => moveImage(img.id, -1)} disabled={idx === 0} className="px-1">↑</button>
                  <button onClick={() => moveImage(img.id, 1)} disabled={idx === images.length - 1} className="px-1">↓</button>
                  <button onClick={() => deleteImage(img.id)} className="px-1 text-red-500">×</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t">
          <button onClick={onClose} className="px-4 py-2 border rounded">Cancel</button>
          <button onClick={() => save(false)} disabled={saving} className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
