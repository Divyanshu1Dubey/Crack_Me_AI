'use client';

/**
 * "Build from PYQs" (POST /api/questions/topic-notes/build/): pick exam, subject and topic (or the
 * whole subject / every topic of it), preview with a dry run, then build. Builds write unpublished
 * drafts only and never change an answer key (questions/notes_builder.py); excluded PYQs (no key,
 * disputed, scholarship, open report, ...) are listed with their reasons, never cited.
 */
import { useState } from 'react';
import { Eye, Hammer, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FormattedText } from '@/components/FormattedText';
import { notesAPI } from '@/lib/notesAPI';
import { useSubjectTopics, type AdminSubject } from '../_lib/useAdminTaxonomy';
import {
  BUILD_EXAMS,
  BUILD_MODES,
  DEFAULT_BUILD_FORM,
  PROVISIONAL_MARK,
  buildActionLabel,
  buildErrorLabel,
  buildPayload,
  describeNotesError,
  examLabel,
  reasonLabel,
  summarizeBuild,
  warningLabel,
  type BuildForm,
  type BuildReport,
  type BuildReportRow,
  type BuilderStatus,
} from '@/components/notes/notesData';

const CONTROL = 'mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm text-foreground';

function actionTone(action: string): 'success' | 'secondary' | 'warning' | 'outline' {
  if (action === 'create' || action === 'update') return 'success';
  if (action === 'skipped') return 'warning';
  return 'secondary';
}

function ReportRow({ row, applied, onOpenNote }: { row: BuildReportRow; applied: boolean; onOpenNote: (id: number) => void }) {
  const counts = row.counts || {};
  // A built row lists why PYQs were left out; a skipped one, every candidate by key status
  // ('excluded:no_key', 'provisional:unverified', ...).
  const leftOut = row.excluded_reasons;
  const reasons = leftOut || row.counts_by_reason || {};
  const reasonText = (code: string) => {
    if (leftOut || !code.includes(':')) return reasonLabel(code);
    const [status, reason] = code.split(':');
    return `${status} · ${reasonLabel(reason)}`;
  };
  return (
    <li className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-1.5 text-sm">
        <Badge variant={actionTone(row.action)}>{buildActionLabel(row.action, applied)}</Badge>
        <span className="min-w-0 break-words font-medium">
          {examLabel(row.exam_type, row.is_combined)} · {row.subject}{row.topic ? ` › ${row.topic}` : ' (whole subject)'}
        </span>
        {row.method && row.action !== 'skipped' && <span className="text-xs text-muted-foreground">{row.method}</span>}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {row.eligible_pyqs} dated PYQs
        {typeof counts.cited === 'number' && ` · ${counts.cited} cited (${counts.verified ?? 0} verified, ${counts.provisional ?? 0} provisional ${PROVISIONAL_MARK})`}
        {typeof counts.excluded === 'number' && ` · ${counts.excluded} excluded`}
        {typeof counts.points === 'number' && ` · ${counts.points} points, ${counts.repeated_points ?? 0} repeated`}
        {typeof counts.evidence_points === 'number' && counts.evidence_points > 0 && ` · ${counts.evidence_points} with a textbook line`}
      </p>
      {row.error && <p className="mt-1 text-xs text-destructive">{buildErrorLabel(row.error)}</p>}
      {Object.keys(reasons).length > 0 && (
        <ul className="mt-1.5 flex flex-wrap gap-1" aria-label={leftOut ? 'Why PYQs were left out' : 'Candidate PYQs by key status'}>
          {Object.entries(reasons).map(([code, n]) => (
            <li key={code} className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-foreground">
              {reasonText(code)}: {n}
            </li>
          ))}
        </ul>
      )}
      {row.warnings?.length > 0 && (
        <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">{row.warnings.map(warningLabel).join(' · ')}</p>
      )}
      {row.note_id && applied && (
        <Button variant="outline" size="sm" className="mt-2" onClick={() => onOpenNote(row.note_id as number)}>
          Open note #{row.note_id}
        </Button>
      )}
      {row.preview?.markdown && (
        <div className="mt-2 max-h-96 overflow-y-auto break-words rounded-md border border-border bg-background p-3 text-sm">
          <FormattedText text={row.preview.markdown} />
        </div>
      )}
    </li>
  );
}

export interface BuildPanelProps {
  status: BuilderStatus | null;
  subjects: AdminSubject[];
  onBuilt: (report: BuildReport) => void;
  onOpenNote: (id: number) => void;
}

export default function BuildPanel({ status, subjects, onBuilt, onOpenNote }: BuildPanelProps) {
  const [form, setForm] = useState<BuildForm>(DEFAULT_BUILD_FORM);
  const [busy, setBusy] = useState<'dry' | 'build' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<BuildReport | null>(null);
  const [queued, setQueued] = useState<string | null>(null);
  const { ensureTopics, topicsFor, topicsPlaceholder } = useSubjectTopics();

  const set = <K extends keyof BuildForm>(key: K, value: BuildForm[K]) => setForm((f) => ({ ...f, [key]: value }));
  const exam = BUILD_EXAMS.find((e) => e.value === form.exam);
  const mode = BUILD_MODES.find((m) => m.value === form.mode);

  async function run(dryRun: boolean) {
    const payload = buildPayload(form, dryRun);
    if ('error' in payload) {
      setError(payload.error);
      return;
    }
    setBusy(dryRun ? 'dry' : 'build');
    setError(null);
    setQueued(null);
    try {
      const res = await notesAPI.build(payload.body);
      const data = res.data as BuildReport & { queued?: boolean; task_id?: string; notes?: unknown };
      if (res.status === 202 || data.queued) {
        setReport(null);
        setQueued(`Queued ${String(data.notes)} notes for the background worker (task ${String(data.task_id)}). `
          + 'They appear in the library as the worker builds them; the worker (qcluster) must be running.');
        return;
      }
      setReport(data);
      if (!dryRun) onBuilt(data);
    } catch (err) {
      setReport(null);
      setError(describeNotesError(err, 'The build failed.'));
    } finally {
      setBusy(null);
    }
  }

  if (status && !status.enabled) {
    return (
      <section aria-labelledby="build-heading" className="mb-4 rounded-lg border border-border bg-card p-4">
        <h2 id="build-heading" className="text-sm font-semibold text-foreground">Build from PYQs</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The PYQ notes builder is switched off on this server (<code>TOPIC_NOTES_BUILDER</code>). Manual notes below still
          work; &ldquo;Generate&rdquo; uses the AI generator while the builder is off.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="build-heading" className="mb-4 space-y-3 rounded-lg border border-border bg-card p-4 text-foreground">
      <div>
        <h2 id="build-heading" className="text-sm font-semibold">Build from PYQs</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Points are template facts from active, dated PYQs: repeated questions first, each citing its PYQs.
          A point whose key is not verified is marked {PROVISIONAL_MARK}; excluded PYQs are never cited. Builds write unpublished
          drafts and never change an answer key.
          {status?.ai_offline && ' Offline mode: AI rewrites are skipped (extractive notes only).'}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block min-w-0">
          <span className="text-xs text-muted-foreground">Exam</span>
          <select className={CONTROL} value={form.exam} onChange={(e) => set('exam', e.target.value as BuildForm['exam'])}>
            {BUILD_EXAMS.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
          </select>
        </label>
        <label className="block min-w-0">
          <span className="text-xs text-muted-foreground">Subject</span>
          <select
            className={CONTROL}
            value={form.subjectId}
            onChange={(e) => { setForm((f) => ({ ...f, subjectId: e.target.value, topicId: '' })); ensureTopics(e.target.value); }}
          >
            <option value="">Select…</option>
            {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label className="block min-w-0">
          <span className="text-xs text-muted-foreground">Scope</span>
          <select className={CONTROL} value={form.scope} onChange={(e) => set('scope', e.target.value as BuildForm['scope'])}>
            <option value="topic">One topic</option>
            <option value="subject">Whole subject (one note)</option>
            <option value="subject_topics">Every topic of the subject</option>
          </select>
        </label>
        <label className="block min-w-0">
          <span className="text-xs text-muted-foreground">Topic</span>
          <select
            className={CONTROL}
            value={form.topicId}
            onChange={(e) => set('topicId', e.target.value)}
            onFocus={() => ensureTopics(form.subjectId)}
            disabled={!form.subjectId || form.scope !== 'topic'}
          >
            <option value="">
              {form.scope !== 'topic' ? 'Not needed' : !form.subjectId ? 'Pick a subject first' : topicsPlaceholder(form.subjectId, 'Select…')}
            </option>
            {topicsFor(form.subjectId).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label className="block min-w-0">
          <span className="text-xs text-muted-foreground">Mode</span>
          <select className={CONTROL} value={form.mode} onChange={(e) => set('mode', e.target.value as BuildForm['mode'])}>
            {BUILD_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </label>
        <label className="block min-w-0">
          <span className="text-xs text-muted-foreground">Minimum usable PYQs</span>
          <input
            type="number"
            min={1}
            max={50}
            inputMode="numeric"
            className={CONTROL}
            value={form.minQuestions}
            onChange={(e) => set('minQuestions', Number(e.target.value))}
          />
        </label>
      </div>
      <p className="text-xs text-muted-foreground">{exam?.hint} {mode?.hint}</p>

      <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={form.includeProvisional} onChange={(e) => set('includeProvisional', e.target.checked)} />
          <span>State provisional answers (marked {PROVISIONAL_MARK})</span>
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={form.verifiedOnly} onChange={(e) => set('verifiedOnly', e.target.checked)} />
          <span>Verified keys only</span>
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={form.force} onChange={(e) => set('force', e.target.checked)} />
          <span>Rebuild even if unchanged</span>
        </label>
      </div>
      {!form.includeProvisional && !form.verifiedOnly && (
        <p className="text-xs text-muted-foreground">Provisional PYQs are then listed to practise, without their answer.</p>
      )}

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => run(true)} disabled={busy !== null}>
          {busy === 'dry' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
          Preview (dry run)
        </Button>
        <Button size="sm" onClick={() => run(false)} disabled={busy !== null}>
          {busy === 'build' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Hammer className="h-4 w-4" aria-hidden="true" />}
          Build draft notes
        </Button>
      </div>

      {queued && <p role="status" className="rounded-md bg-muted px-3 py-2 text-sm">{queued}</p>}
      {report && (
        <div className="space-y-2" aria-live="polite">
          <p className="text-sm font-medium">
            {report.apply ? 'Built: ' : 'Dry run (nothing saved): '}{summarizeBuild(report)}
          </p>
          <ul className="space-y-2">
            {report.notes.map((row, i) => (
              <ReportRow key={`${row.exam_type}-${row.subject_id}-${row.topic_id ?? 's'}-${i}`} row={row} applied={report.apply} onOpenNote={onOpenNote} />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
