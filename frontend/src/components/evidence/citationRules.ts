/**
 * How a student sees a question's evidence (pure: no network, no DOM; tests/unit imports it).
 *
 * Ground rule (docs/audit/MEDICAL_ACCURACY_DESIGN.md §1.4): students see accepted citations (title,
 * edition, chapter, page label) and snippets of at most 240 characters, never a full page. The backend
 * already enforces that; these rules keep the UI honest if a payload ever carries more.
 */
import type { StudentCitationRaw } from '@/lib/evidenceAPI';

export const SNIPPET_MAX_CHARS = 240;
export const MAX_CITATIONS = 3;

export interface StudentCitationView {
  id: number;
  title: string;
  edition: string;
  year: number | null;
  chapter: string;
  /** 'p. 312' (printed page), 'PDF p. 340' (physical page only) or 'section 4' (DOCX). */
  page: string;
  snippet: string;
  /** 'Supports option A' / 'Argues against option C' / 'States the answer' / ''. */
  stance: string;
  figureUrl: string | null;
}

function text(value: unknown, max = 300): string {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, max) : '';
}

/** One line of at most `max` characters, cut at a word boundary (the ellipsis counts). */
export function clipSnippet(value: unknown, max = SNIPPET_MAX_CHARS): string {
  const line = typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
  if (line.length <= max) return line;
  let cut = line.slice(0, max - 1);
  const space = cut.lastIndexOf(' ');
  if (space > max * 0.6) cut = cut.slice(0, space);
  return `${cut.replace(/[\s,;:]+$/, '')}…`;
}

export function pageText(raw: Pick<StudentCitationRaw, 'page_label' | 'page_note'>): string {
  const label = text(raw.page_label, 32);
  if (label) return `p. ${label}`;
  return text(raw.page_note, 40);
}

export function stanceText(raw: Pick<StudentCitationRaw, 'stance' | 'option_letter'>): string {
  const letter = ['A', 'B', 'C', 'D'].includes(String(raw.option_letter ?? '').toUpperCase())
    ? String(raw.option_letter).toUpperCase()
    : '';
  switch (raw.stance) {
    case 'supports':
      return letter ? `Supports option ${letter}` : 'Supports the answer';
    case 'contradicts':
      return letter ? `Argues against option ${letter}` : '';
    case 'states_key':
      return 'States the answer';
    default:
      return '';
  }
}

/** Only the evidence figure endpoint (signed crop), absolute http(s) or root-relative. */
export function safeFigureUrl(value: unknown): string | null {
  if (typeof value !== 'string' || !value) return null;
  try {
    const url = new URL(value, 'http://relative.invalid');
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    if (!/^\/api\/evidence\/figures\/\d+\/$/.test(url.pathname)) return null;
    return url.host === 'relative.invalid' ? `${url.pathname}${url.search}` : url.href;
  } catch {
    return null;
  }
}

/** The citations to show: [] for a locked or malformed answer; at most MAX_CITATIONS, each clipped. */
export function normalizeCitations(payload: unknown): StudentCitationView[] {
  if (!payload || typeof payload !== 'object') return [];
  const body = payload as { citations?: unknown; locked?: unknown };
  if (body.locked === true || !Array.isArray(body.citations)) return [];
  const seen = new Set<number>();
  const out: StudentCitationView[] = [];
  for (const entry of body.citations) {
    if (!entry || typeof entry !== 'object') continue;
    const raw = entry as StudentCitationRaw;
    const id = Number(raw.id);
    const title = text(raw.source?.title) || text(raw.citation);
    if (!Number.isFinite(id) || seen.has(id) || !title) continue;
    seen.add(id);
    out.push({
      id,
      title,
      edition: text(raw.source?.edition, 60),
      year: typeof raw.source?.year === 'number' ? raw.source.year : null,
      chapter: text(raw.chapter, 200),
      page: pageText(raw),
      snippet: clipSnippet(raw.snippet),
      stance: stanceText(raw),
      figureUrl: safeFigureUrl(raw.figure_url),
    });
    if (out.length >= MAX_CITATIONS) break;
  }
  return out;
}

/** 'Nelson Textbook of Pediatrics, 21st ed. (2020)' -- the line under which a citation is shown. */
export function sourceLine(view: Pick<StudentCitationView, 'title' | 'edition' | 'year'>): string {
  let line = view.title;
  if (view.edition) line += `, ${/\bed(ition)?\.?$/i.test(view.edition) ? view.edition : `${view.edition} ed.`}`;
  if (view.year && !line.includes(String(view.year))) line += ` (${view.year})`;
  return line;
}
