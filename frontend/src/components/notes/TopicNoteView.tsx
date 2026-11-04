'use client';

/**
 * One topic note as a student reads it (also the admin preview).
 *
 * Built notes (detail route): sections of points; each point shows its answer, a clear
 * "Provisional — answer key not yet verified" badge when the key behind it is not verified, the
 * sittings it was asked in, its source PYQs (each a link to practise that question), the reviewed
 * "why" line and at most one verbatim textbook line with its citation. Manual notes, or a built note
 * read while the server's builder flag is off, render their markdown through FormattedText (the
 * server already filtered it for this viewer and kept the ⚠ marks). Points the viewer's plan does
 * not include are counted, never sent (`locked_points`).
 */
import Link from 'next/link';
import { AlertTriangle, BadgeCheck, Lock, Repeat } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FormattedText } from '@/components/FormattedText';
import {
  PROVISIONAL_HINT,
  PROVISIONAL_LABEL,
  PROVISIONAL_LEGEND,
  PROVISIONAL_MARK,
  VERIFIED_LABEL,
  askedLine,
  hasProvisionalPoints,
  hiddenNotice,
  isProvisional,
  lockedTeaser,
  pointSources,
  practiceHref,
  practiceReasonLabel,
  sectionsWithPoints,
  sourceChipLabel,
  spokenSittingLabel,
  type NotePoint,
  type PublishedNote,
} from './notesData';

export function KeyStatusBadge({ status }: { status: string }) {
  if (!isProvisional(status)) {
    return (
      <Badge variant="success" className="gap-1">
        <BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />
        {VERIFIED_LABEL}
      </Badge>
    );
  }
  return (
    <Badge variant="warning" className="gap-1 whitespace-normal text-left" title={PROVISIONAL_HINT}>
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {PROVISIONAL_LABEL}
    </Badge>
  );
}

function SourceChips({ point }: { point: NotePoint }) {
  const sources = pointSources(point);
  if (!sources.length) return null;
  return (
    <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label="Source PYQs">
      {sources.map((source) => {
        const provisional = isProvisional(source.key_status);
        const spoken = source.label ? ` (${spokenSittingLabel(source.label)})` : '';
        return (
          <li key={source.id} className="min-w-0">
            <Link
              href={practiceHref(source.id)}
              className="inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-background px-2.5 py-1 text-xs text-foreground hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Practise question ${source.id}${spoken}${provisional ? ', answer key not yet verified' : ''}`}
            >
              <span className="truncate">{sourceChipLabel(source)}</span>
              {provisional && <span aria-hidden="true" className="text-amber-600 dark:text-amber-400">{PROVISIONAL_MARK}</span>}
              <span className="text-muted-foreground" aria-hidden="true">· Practise</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function PointCard({ point }: { point: NotePoint }) {
  const fact = point.kind === 'fact';
  const asked = askedLine(point);
  const evidence = (point.evidence ?? [])[0];
  return (
    <li className="rounded-lg border border-border bg-card p-3 sm:p-4">
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        {fact ? (
          <KeyStatusBadge status={point.key_status} />
        ) : (
          <Badge variant="outline" className="whitespace-normal text-left">{practiceReasonLabel(point.practice_reason)}</Badge>
        )}
        {point.frequency > 1 && (
          <Badge variant="secondary" className="gap-1">
            <Repeat className="h-3 w-3" aria-hidden="true" />
            Asked {point.frequency}×
          </Badge>
        )}
      </div>
      {fact ? (
        <p className="break-words text-sm leading-relaxed text-foreground sm:text-base">
          <span>{point.stem}</span>{' '}
          <span aria-hidden="true">→</span>
          <span className="sr-only">Answer:</span>{' '}
          <strong className="font-semibold">{point.answer}</strong>
        </p>
      ) : (
        <p className="break-words text-sm leading-relaxed text-muted-foreground">{point.stem}</p>
      )}
      {fact && point.why && (
        <p className="mt-1.5 break-words text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Why: </span>
          {point.why}
        </p>
      )}
      {fact && evidence?.excerpt && (
        <blockquote className="mt-2 border-l-2 border-border pl-3 text-sm text-muted-foreground">
          <p className="break-words">
            &ldquo;{evidence.excerpt}{evidence.truncated ? '…' : ''}&rdquo;
          </p>
          {evidence.label && (
            <footer className="mt-1 text-xs">
              <cite className="break-words">{evidence.label}</cite>
            </footer>
          )}
        </blockquote>
      )}
      <div className="mt-2">
        {asked && <p className="text-xs text-muted-foreground">{asked}</p>}
        <SourceChips point={point} />
      </div>
    </li>
  );
}

function LockedCard({ text, detail, onUpgrade }: { text: string; detail: string; onUpgrade?: () => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4 sm:flex-row sm:items-center">
      <Lock className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-foreground">{text}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
      </div>
      {onUpgrade && (
        <Button size="sm" onClick={onUpgrade} className="shrink-0">
          Unlock with Premium
        </Button>
      )}
    </div>
  );
}

export interface TopicNoteViewProps {
  note: PublishedNote;
  /** Opens the upgrade flow (shown with the locked-points teaser). */
  onUpgrade?: () => void;
}

export default function TopicNoteView({ note, onUpgrade }: TopicNoteViewProps) {
  const sections = sectionsWithPoints(note);
  // The detail route sends the points of a built note (possibly none this viewer may read).
  const detailed = Array.isArray(note.points);
  const structured = detailed && sections.length > 0;
  const teaser = lockedTeaser(note.locked_points);
  const hidden = hiddenNotice(note.hidden_points);
  // The legend only next to something it explains: a provisional point, or ⚠ in the markdown.
  const showLegend = structured
    ? hasProvisionalPoints(note)
    : !detailed && (note.content ?? '').includes(PROVISIONAL_MARK);
  const withheld = note.answers_locked && !structured && !(note.content ?? '').trim();

  return (
    <div className="space-y-4 text-foreground">
      {showLegend && (
        <p className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            <strong>{PROVISIONAL_MARK} Provisional</strong> {PROVISIONAL_LEGEND}
          </span>
        </p>
      )}
      {hidden && (
        <p role="status" className="rounded-lg border border-border bg-muted/50 p-3 text-sm text-muted-foreground">{hidden}</p>
      )}
      {!hidden && note.is_stale && (
        <p role="status" className="rounded-lg border border-border bg-muted/50 p-3 text-sm text-muted-foreground">
          A source question changed since this note was written; it may be out of date.
        </p>
      )}

      {withheld ? (
        <LockedCard
          text="This note is part of Premium"
          detail="It restates the answers of premium PYQs. Premium shows every note with its source questions."
          onUpgrade={onUpgrade}
        />
      ) : structured ? (
        sections.map(({ section, points }) => (
          <section key={section.id ?? section.title} aria-label={section.title} className="space-y-2">
            <h2 className="text-base font-semibold text-foreground sm:text-lg">{section.title}</h2>
            <ul className="space-y-2">
              {points.map((point) => <PointCard key={point.id} point={point} />)}
            </ul>
          </section>
        ))
      ) : detailed ? (
        !teaser && !hidden && <p className="text-sm text-muted-foreground">This note has no points yet.</p>
      ) : (
        <div className="min-w-0 break-words text-sm leading-relaxed text-foreground">
          <FormattedText text={note.content} />
        </div>
      )}

      {teaser && !withheld && (
        <LockedCard
          text={teaser}
          detail="Premium shows every point of this note, with its source PYQs and answer keys."
          onUpgrade={onUpgrade}
        />
      )}
    </div>
  );
}
