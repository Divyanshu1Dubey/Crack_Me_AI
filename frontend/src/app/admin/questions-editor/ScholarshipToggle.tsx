'use client';

/**
 * Scholarship challenge membership of one question (admin questions editor, 2026-11-07).
 *
 * Saved at once through PATCH /questions/<id>/scholarship/ -- not with the form's Save, because the
 * flag is never part of a student payload (it would name the challenge questions). The server refuses
 * a question the challenge cannot show fairly: the challenge shows the stem and four options only, and
 * a student needs 5/5. Joining the pool does not verify the key.
 */
import React, { useState } from 'react';
import { questionsAPI } from '@/lib/api';
import { scholarshipToggleError } from '../_lib/adminHelpers';

interface ScholarshipToggleProps {
  questionId: number;
  initial: boolean;
  onChanged: (eligible: boolean) => void;
}

export default function ScholarshipToggle({ questionId, initial, onChanged }: ScholarshipToggleProps) {
  const [eligible, setEligible] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [poolSize, setPoolSize] = useState<number | null>(null);

  async function toggle(next: boolean) {
    setSaving(true);
    setError(null);
    try {
      const res = await questionsAPI.setScholarship(questionId, next);
      setEligible(res.data.is_scholarship_eligible);
      setPoolSize(typeof res.data.pool_size === 'number' ? res.data.pool_size : null);
      onChanged(res.data.is_scholarship_eligible);
    } catch (err) {
      setError(scholarshipToggleError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded border border-amber-300/70 dark:border-amber-500/40 bg-amber-50/60 dark:bg-amber-950/20 p-3 text-sm text-gray-900 dark:text-slate-100">
      <label className="flex items-center gap-2 font-medium">
        <input
          type="checkbox"
          className="accent-amber-600"
          checked={eligible}
          disabled={saving}
          onChange={(e) => void toggle(e.target.checked)}
        />
        In the scholarship challenge
        {saving && <span className="text-xs text-gray-500 dark:text-slate-400">saving…</span>}
      </label>
      <p className="mt-1 text-xs text-gray-600 dark:text-slate-400">
        Saved immediately. Students see only the question text and the four options and need 5/5, so the
        key must be certain and the question must not need a figure. Five active questions open the challenge.
        {poolSize !== null && ` The pool now has ${poolSize} active question${poolSize === 1 ? '' : 's'}.`}
      </p>
      {error && <p role="alert" className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
