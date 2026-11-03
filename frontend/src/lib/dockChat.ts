/**
 * dockChat — pure helpers for the FloatingDock "Ask AI" panel
 * (POST /questions/chat/, questions.views.ChatAssistantView).
 *
 * The endpoint answers with one of:
 *   - 200 `{ reply }`                                   AI answer
 *   - 200 `{ reply, offline: true, citations, ... }`    grounded extract from
 *     the textbook library, no AI model, not charged (AI_OFFLINE_MODE or
 *     every provider down)
 *   - 503 `{ code: 'ai_unavailable', message }`         nothing to answer
 *     with; not charged
 *   - 402 `{ code: 'upgrade_required', message }`       free daily AI cap
 *     (api.ts also opens the global upgrade modal)
 *   - 429 `{ error: 'insufficient_tokens', message }`   or a DRF throttle
 *     `{ detail }`
 *
 * Kept free of React/Next imports so tests/unit can load it with node --test.
 */

export interface DockCitation {
  book: string;
  page: string;
}

export interface DockReply {
  text: string;
  offline: boolean;
  citations: DockCitation[];
}

export type DockNoticeKind = 'unavailable' | 'upgrade' | 'limit' | 'error';

export interface DockNotice {
  kind: DockNoticeKind;
  text: string;
  href?: string;
  linkLabel?: string;
}

export const AI_UNAVAILABLE_TEXT =
  'AI is unavailable right now. You were not charged. Please try again in a few minutes.';
export const NETWORK_ERROR_TEXT = 'Could not reach the server. Check your connection and try again.';
export const GENERIC_ERROR_TEXT = 'The AI assistant could not answer. Please try again.';
export const EMPTY_REPLY_TEXT = 'No answer came back. Please try again.';

const MAX_CITATIONS = 5;

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

/** Book/page pairs from the reply's `citations` (deduplicated, at most 5). */
export function parseDockCitations(raw: unknown): DockCitation[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: DockCitation[] = [];
  for (const item of raw) {
    const c = record(item);
    const book = text(c.book);
    if (!book) continue;
    const page = typeof c.page === 'number' && Number.isFinite(c.page) ? String(c.page) : text(c.page);
    const key = `${book}\u0000${page}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ book, page });
    if (out.length >= MAX_CITATIONS) break;
  }
  return out;
}

/**
 * The offline extract starts with a "> Offline answer: ..." quote; the
 * panel shows its own offline badge, so that first quote is dropped.
 */
export function stripOfflineNotice(reply: string): string {
  const lines = reply.split('\n');
  if (!/^>\s*Offline answer\b/i.test(lines[0] ?? '')) return reply;
  let i = 0;
  while (i < lines.length && lines[i].startsWith('>')) i += 1;
  const rest = lines.slice(i).join('\n').trim();
  return rest || reply;
}

/** A displayable reply from a 200 response body, or null when it has none. */
export function parseDockReply(data: unknown): DockReply | null {
  const body = record(data);
  const reply = text(body.reply);
  if (!reply) return null;
  const offline = body.offline === true;
  return {
    text: offline ? stripOfflineNotice(reply) : reply,
    offline,
    citations: parseDockCitations(body.citations),
  };
}

/** What to tell the user when POST /questions/chat/ failed. */
export function dockErrorNotice(err: unknown): DockNotice {
  const response = record(err).response;
  if (!response || typeof response !== 'object') {
    return { kind: 'error', text: NETWORK_ERROR_TEXT };
  }
  const res = record(response);
  const status = typeof res.status === 'number' ? res.status : 0;
  const data = record(res.data);
  const code = text(data.code);
  const message = text(data.message);

  if (code === 'ai_unavailable' || status === 503) {
    return { kind: 'unavailable', text: message || AI_UNAVAILABLE_TEXT };
  }
  if (code === 'upgrade_required' || status === 402) {
    return {
      kind: 'upgrade',
      text: message || 'Your free AI messages for today are used up. Premium removes the daily limit.',
      href: '/subscription',
      linkLabel: 'See plans',
    };
  }
  if (status === 429) {
    if (text(data.error) === 'insufficient_tokens') {
      return {
        kind: 'limit',
        text: message || "You don't have enough AI tokens for this.",
        href: '/tokens',
        linkLabel: 'Get tokens',
      };
    }
    return {
      kind: 'limit',
      text: text(data.detail) || message || 'Too many AI requests. Please wait a moment and try again.',
    };
  }
  return { kind: 'error', text: GENERIC_ERROR_TEXT };
}
