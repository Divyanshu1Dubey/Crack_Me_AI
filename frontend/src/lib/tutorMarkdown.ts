/**
 * How AI Tutor answers are turned into readable HTML (2026-11).
 *
 * The answers are markdown written by several models: GitHub tables with `<br>` inside cells, `[PYQ 2019]`
 * / `[High Yield]` tags, `**Textbook Reference: ...**` lines. The page used plain CommonMark, so every
 * table came out as a run of `|` characters and every `<br>` as literal text.
 *
 * - `normalizeTutorMarkdown` repairs the shapes models produce: a table glued to the sentence before it
 *   (a GFM table needs its own block), a table whose rows were joined on one line (`| a | b | |---|---| | 1 |`).
 * - `tutorRemarkPlugins` / `tutorRehypePlugins` are the pipeline: GFM (tables, one-tilde text kept as is),
 *   raw HTML parsed then reduced to formatting tags by the shared allow-list (`markdownSanitize`), then
 *   `rehypeTutorTags` turns the tags into styled badges without flattening the paragraph around them.
 *
 * Pure: no React, no DOM (tests/unit/tutor-markdown.test.ts renders it with react-dom/server).
 */
import type { Element, ElementContent, Root, Text } from 'hast';
import type { Options } from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { rehypeAllowlist } from './markdownSanitize';

const DELIM_CELL = String.raw`\s*:?-{3,}:?\s*`;
/** A whole delimiter row: `|---|:---:|`. */
const DELIM_ROW_RE = new RegExp(String.raw`^\s*\|?(?:${DELIM_CELL}\|)+${DELIM_CELL}\|?\s*$`);
/** A delimiter run inside a longer line (a table squashed onto one line). */
const INLINE_DELIM_RE = new RegExp(String.raw`\|(?:${DELIM_CELL}\|){1,}`);
const ROW_RE = /^\s*\|.*\|\s*$/;

function isRow(line: string): boolean {
  return ROW_RE.test(line);
}

/** Rebuild a table that was joined onto one line, using the delimiter row to know the column count. */
function splitSquashedTable(line: string): string[] | null {
  const match = INLINE_DELIM_RE.exec(line);
  if (!match || match.index === 0 && line.trim().length === match[0].trim().length) return null;
  const columns = (match[0].match(/-{3,}/g) || []).length;
  if (columns < 2) return null;
  const before = line.slice(0, match.index);
  const after = line.slice(match.index + match[0].length);
  // Header: the last `columns` cells before the delimiter run.
  const headParts = before.split('|');
  if (headParts.length < columns + 1) return null;
  const header = headParts.slice(-(columns + 1), -1);
  const lead = headParts.slice(0, -(columns + 1)).join('|').trim();
  // Body: rows of `columns` cells, joined by "| |" (one empty boundary cell between rows).
  const bodyParts = after.split('|');
  if (bodyParts.length && !bodyParts[0].trim()) bodyParts.shift();
  const rows: string[][] = [];
  let index = 0;
  while (index + columns <= bodyParts.length) {
    const row = bodyParts.slice(index, index + columns);
    if (row.every((cell) => !cell.trim())) break;
    rows.push(row);
    index += columns;
    if (index < bodyParts.length && !bodyParts[index].trim()) index += 1;   // the boundary between rows
  }
  const tail = bodyParts.slice(index).join('|').trim();
  const out: string[] = [];
  if (lead) out.push(lead, '');
  out.push(`| ${header.map((c) => c.trim()).join(' | ')} |`);
  out.push(`|${Array(columns).fill('---').join('|')}|`);
  for (const row of rows) out.push(`| ${row.map((c) => c.trim()).join(' | ')} |`);
  if (tail) out.push('', tail);
  return out;
}

/** Repair the markdown shapes AI models produce so tables render as tables. */
export function normalizeTutorMarkdown(input: string): string {
  const lines = (input || '').replace(/\r\n?/g, '\n').split('\n');
  const expanded: string[] = [];
  for (const line of lines) {
    const split = !DELIM_ROW_RE.test(line) && INLINE_DELIM_RE.test(line) ? splitSquashedTable(line) : null;
    expanded.push(...(split ?? [line]));
  }
  const out: string[] = [];
  for (let i = 0; i < expanded.length; i += 1) {
    const line = expanded[i];
    const next = expanded[i + 1] ?? '';
    const prev = out.length ? out[out.length - 1] : '';
    // A table header (row followed by a delimiter row) needs a blank line before it.
    if (isRow(line) && DELIM_ROW_RE.test(next) && prev.trim() && !isRow(prev)) out.push('');
    // Text right after a table row starts a new block.
    if (line.trim() && !isRow(line) && !DELIM_ROW_RE.test(line) && isRow(prev)) out.push('');
    out.push(line);
  }
  return out.join('\n');
}

// --------------------------------------------------------------------------- badges

const TAG_RE = /(\[PYQ\s+\d{4}\]|\[High[ -]Yield\])/gi;
const SKIP_TAGS = new Set(['code', 'pre', 'a']);

function textOf(node: ElementContent): string {
  if (node.type === 'text') return node.value;
  if (node.type === 'element') return node.children.map(textOf).join('');
  return '';
}

function badge(label: string, tone: 'pink' | 'amber'): Element {
  return {
    type: 'element',
    tagName: 'span',
    properties: { className: ['ai-tag', `ai-tag-${tone}`] },
    children: [{ type: 'text', value: label }],
  };
}

function splitText(node: Text): ElementContent[] {
  const parts = node.value.split(TAG_RE);
  if (parts.length === 1) return [node];
  return parts.filter(Boolean).map((part): ElementContent => {
    if (/^\[PYQ\s+\d{4}\]$/i.test(part)) return badge(`📋 ${part.slice(1, -1).replace(/\s+/g, ' ')}`, 'pink');
    if (/^\[High[ -]Yield\]$/i.test(part)) return badge('🔥 HIGH YIELD', 'amber');
    return { type: 'text', value: part };
  });
}

function walk(node: Root | Element): void {
  const children: ElementContent[] = [];
  for (const child of node.children as ElementContent[]) {
    if (child.type === 'text') {
      children.push(...splitText(child));
      continue;
    }
    if (child.type === 'element') {
      if (child.tagName === 'strong' && /^\s*Textbook Reference/i.test(textOf(child))) {
        child.properties = { ...child.properties, className: ['ai-tag', 'ai-tag-green'] };
        child.children = [{ type: 'text', value: `📚 ${textOf(child).trim()}` }];
      } else if (!SKIP_TAGS.has(child.tagName)) {
        walk(child);
      }
    }
    children.push(child);
  }
  (node as Element).children = children;
}

/** Badges for `[PYQ 2019]`, `[High Yield]` and `**Textbook Reference ...**`. Runs after the allow-list,
 *  so its class names survive. */
export function rehypeTutorTags() {
  return (tree: Root) => {
    walk(tree);
  };
}

export const tutorRemarkPlugins: Options['remarkPlugins'] = [[remarkGfm, { singleTilde: false }], remarkBreaks];
export const tutorRehypePlugins: Options['rehypePlugins'] = [rehypeRaw, rehypeAllowlist, rehypeTutorTags];
