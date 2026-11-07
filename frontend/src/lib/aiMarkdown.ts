/**
 * AI-written markdown outside the AI Tutor chat (2026-11): study plans, high-yield lists, generated
 * MCQs and AI explanations.
 *
 * Those answers are markdown (GFM tables with `<br>` inside cells, `**bold**`, `*italics*`, lists).
 * The study plan used to be split line by line and every line shown as a checklist item, so table
 * rows, `**`, `|---|` and `<br>` appeared as plain text. Now:
 *  - `prepareAiMarkdown` unwraps ```markdown fences and applies the AI Tutor's table repairs
 *    (`normalizeTutorMarkdown`); `components/ai/AiMarkdown.tsx` hands the result to the shared
 *    `FormattedText` renderer (remark-gfm + remark-breaks, the markdownSanitize allow-list);
 *  - `splitMarkdownSections` cuts a long answer into cards on its headings (bodies stay markdown);
 *  - `plainInline` turns a short markdown label (a card title, a topic name) into plain text.
 *
 * Pure: no React, no DOM (tests/unit/ai-markdown.test.ts).
 */
import { normalizeTutorMarkdown } from './tutorMarkdown';

const FENCE_RE = /^\s{0,3}(`{3,}|~{3,})(.*)$/;
/** A fence labelled markdown / md anywhere in the answer: the model wrapped its markdown. */
const MARKDOWN_FENCE_RE = /^(`{3,}|~{3,})[ \t]*(?:markdown|md)[ \t]*\n([\s\S]*?)\n\1[ \t]*$/gim;
/** The whole answer inside one unlabelled fence. */
const WHOLE_FENCE_RE = /^(`{3,}|~{3,})[ \t]*\n([\s\S]*)\n\1[ \t]*$/;
/** `## Title` / `## Title ##` (a closing run of `#` needs a space before it). */
const ATX_RE = /^\s{0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$/;
/** A line that is nothing but bold text: `**Phase 1 (Foundation)**`, `**Daily Schedule:**`. */
const BOLD_LINE_RE = /^\s{0,3}(\*\*|__)(?!\s)((?:(?!\1).)+?)\1\s*:?\s*$/;
/** `---`, `***`, `___` (spaces allowed between the characters). */
const THEMATIC_BREAK_RE = /^\s{0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;

/** Remove the code fences a model puts around its markdown (a fenced answer showed as raw code). */
export function unwrapMarkdownFence(text: string): string {
  const source = (text || '').replace(/\r\n?/g, '\n').trim();
  const unfenced = source.replace(MARKDOWN_FENCE_RE, (_m, _fence: string, inner: string) => inner);
  const whole = WHOLE_FENCE_RE.exec(unfenced);
  if (!whole) return unfenced;
  const [, fence, inner] = whole;
  // Another fence line inside: these are separate code blocks, not one wrapper.
  const innerFence = fence[0] === '`' ? /^\s{0,3}`{3,}/m : /^\s{0,3}~{3,}/m;
  return innerFence.test(inner) ? unfenced : inner.trim();
}

/**
 * Markdown from an AI model, repaired for the shared renderer (see the module comment). Image links a
 * model writes are usually invented and would load other sites, so only their description is kept,
 * as on the AI Tutor page.
 */
export function prepareAiMarkdown(text: string): string {
  const withoutImages = unwrapMarkdownFence(text).replace(
    /!\[([^\]]*)\]\([^)]*\)/g,
    (_m, alt: string) => (alt.trim() ? `*[${alt.trim()}]*` : ''),
  );
  return normalizeTutorMarkdown(withoutImages);
}

/**
 * A short markdown label as plain text: no `**`, backticks, HTML tags, link syntax or trailing colon.
 * Accepts any value (model JSON sometimes sends a number, e.g. a page) and never throws.
 */
export function plainInline(text: unknown): string {
  const source = typeof text === 'string' ? text : text === null || text === undefined ? '' : String(text);
  return source
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<\/?[a-z][^>]*>/gi, '')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/`+/g, '')
    .replace(/\*+/g, '')
    .replace(/(^|\s)_+(?=\S)/g, '$1')
    .replace(/(\S)_+(?=\s|$|[.,:;!?)])/g, '$1')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\s*:+$/, '');
}

export interface MarkdownSection {
  /** The heading as plain text. */
  title: string;
  /** The markdown under the heading, up to the next section heading. */
  body: string;
}

export interface SplitMarkdown {
  /** A single top heading that names the whole answer (`# 60-Day Plan`), else null. */
  title: string | null;
  /** Markdown before the first section heading. */
  intro: string;
  sections: MarkdownSection[];
}

interface Heading {
  line: number;
  level: number;
  text: string;
}

/** Leading / trailing blank lines and `---` separators are not part of a card's body. */
function trimBlock(lines: string[]): string {
  let start = 0;
  let end = lines.length;
  while (start < end && (!lines[start].trim() || THEMATIC_BREAK_RE.test(lines[start]))) start += 1;
  while (end > start && (!lines[end - 1].trim() || THEMATIC_BREAK_RE.test(lines[end - 1]))) end -= 1;
  return lines.slice(start, end).join('\n');
}

/** `#` headings and bold-only lines outside code fences. */
function findHeadings(lines: string[]): { atx: Heading[]; bold: Heading[] } {
  const atx: Heading[] = [];
  const bold: Heading[] = [];
  let fence: string | null = null;
  lines.forEach((line, index) => {
    const fenceMatch = FENCE_RE.exec(line);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (fence === null) fence = marker;
      else if (marker[0] === fence[0] && marker.length >= fence.length && !fenceMatch[2].trim()) fence = null;
      return;
    }
    if (fence !== null) return;
    const heading = ATX_RE.exec(line);
    if (heading) {
      const text = plainInline(heading[2]);
      if (text) atx.push({ line: index, level: heading[1].length, text });
      return;
    }
    const boldLine = BOLD_LINE_RE.exec(line);
    if (boldLine) {
      const text = plainInline(boldLine[2]);
      if (text) bold.push({ line: index, level: 7, text });
    }
  });
  return { atx, bold };
}

/**
 * Split a long AI answer into sections on its headings.
 *
 * Sections start at the shallowest heading level used. When the answer opens with the only heading of
 * that level (its own title, `# 60-Day Plan`), that heading becomes `title` and the next level splits
 * the sections. Without `#` headings, lines that are nothing but bold text (two or more) split it.
 * Headings inside code fences are ignored and deeper headings stay in the section body. An answer
 * without headings comes back whole as `intro`.
 */
export function splitMarkdownSections(markdown: string): SplitMarkdown {
  const lines = unwrapMarkdownFence(markdown).split('\n');
  const { atx, bold } = findHeadings(lines);

  let title: string | null = null;
  let titleLine = -1;
  let splitters: Heading[] = [];
  if (atx.length) {
    const minLevel = Math.min(...atx.map((h) => h.level));
    const top = atx.filter((h) => h.level === minLevel);
    const deeper = atx.filter((h) => h.level > minLevel);
    if (top.length === 1 && top[0] === atx[0] && deeper.length) {
      title = top[0].text;
      titleLine = top[0].line;
      const nextLevel = Math.min(...deeper.map((h) => h.level));
      splitters = deeper.filter((h) => h.level === nextLevel);
    } else {
      splitters = top;
    }
  } else if (bold.length >= 2) {
    splitters = bold;
  }

  if (!splitters.length) return { title: null, intro: trimBlock(lines), sections: [] };

  const introLines = lines.slice(0, splitters[0].line).filter((_, i) => i !== titleLine);
  const sections = splitters.map((heading, i) => {
    const end = i + 1 < splitters.length ? splitters[i + 1].line : lines.length;
    return { title: heading.text, body: trimBlock(lines.slice(heading.line + 1, end)) };
  });
  return { title, intro: trimBlock(introLines), sections };
}
