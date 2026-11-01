/**
 * Global app shell, wave 3 (Z1):
 *  - dockChat: the FloatingDock "Ask AI" reply / error contract
 *    (offline extract + citations, 503 ai_unavailable, 402, 429)
 *  - Header: Unlimited token pill (C12), no phone logo under the search button
 *  - ExamSwitcher: exam names (UPSC CMS / NEET PG / INI-CET) on 390px phones
 *  - AppShell everywhere (C6): Import Center + ingestion layouts, no nested
 *    <main> in the analytics dashboard_v3 / heatmap pages
 *  - globals.css cascade: sidebar links, glass cards, section titles, badges
 *    and stat cards yield to utilities; select.input-field never clips
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/app-shell-wave3.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  AI_UNAVAILABLE_TEXT,
  GENERIC_ERROR_TEXT,
  NETWORK_ERROR_TEXT,
  dockErrorNotice,
  parseDockCitations,
  parseDockReply,
  stripOfflineNotice,
} from '../../src/lib/dockChat.ts';
import { getPageTitle } from '../../src/lib/appShellRoutes.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');

// ── FloatingDock chat contract ─────────────────────────────────────────────

const OFFLINE_REPLY = [
  '> Offline answer: the AI tutor is unavailable right now, so this was assembled from the textbook library and question bank without an AI model. No tokens were charged.',
  '',
  '**From the textbook library**',
  '- Beta blockers reduce mortality after MI. *[Harrison p. 1502]*',
].join('\n');

test('parseDockReply: an AI answer is shown as is', () => {
  assert.deepEqual(parseDockReply({ reply: '  **Answer**: B  ' }), { text: '**Answer**: B', offline: false, citations: [] });
});

test('parseDockReply: offline extract is labelled, its notice quote dropped, sources kept', () => {
  const reply = parseDockReply({
    reply: OFFLINE_REPLY,
    offline: true,
    offline_reason: 'providers_down',
    charged: false,
    citations: [
      { book: 'Harrison', page: 1502, excerpt: 'Beta blockers…', relevance: 0.8 },
      { book: 'Harrison', page: '1502' },
      { book: '  ', page: 3 },
      { book: 'Bailey & Love', page: '' },
    ],
  });
  assert.ok(reply);
  assert.equal(reply.offline, true);
  assert.ok(reply.text.startsWith('**From the textbook library**'), reply.text);
  assert.doesNotMatch(reply.text, /^>/m);
  assert.deepEqual(reply.citations, [
    { book: 'Harrison', page: '1502' },
    { book: 'Bailey & Love', page: '' },
  ]);
});

test('parseDockReply: nothing to show yields null (never an outage sentence)', () => {
  for (const body of [{}, { reply: '' }, { reply: '   ' }, { reply: 42 }, null, undefined, 'text', []]) {
    assert.equal(parseDockReply(body), null, JSON.stringify(body));
  }
});

test('stripOfflineNotice: only a leading offline notice is removed', () => {
  assert.equal(stripOfflineNotice('> Offline answer: x\n> more\n\nBody'), 'Body');
  assert.equal(stripOfflineNotice('> A quoted PYQ stem\n\nBody'), '> A quoted PYQ stem\n\nBody');
  // A reply that is only the notice stays as it is rather than going blank.
  assert.equal(stripOfflineNotice('> Offline answer: x'), '> Offline answer: x');
});

test('parseDockCitations: at most five, non-arrays ignored', () => {
  const many = Array.from({ length: 9 }, (_, i) => ({ book: `Book ${i}`, page: i }));
  assert.equal(parseDockCitations(many).length, 5);
  assert.deepEqual(parseDockCitations({ book: 'x' }), []);
  assert.deepEqual(parseDockCitations(undefined), []);
});

const axiosError = (status: number, data?: unknown) => ({ response: { status, data } });

test('dockErrorNotice: 503 ai_unavailable shows the server message, never charged', () => {
  const message = 'The AI tutor is unavailable right now and no grounded offline answer was found for this question. You were not charged. Please try again in a few minutes.';
  assert.deepEqual(
    dockErrorNotice(axiosError(503, { code: 'ai_unavailable', message, offline: false, charged: false })),
    { kind: 'unavailable', text: message },
  );
  // A bare 503 (proxy / no body) still reads as "AI is unavailable".
  assert.deepEqual(dockErrorNotice(axiosError(503)), { kind: 'unavailable', text: AI_UNAVAILABLE_TEXT });
  assert.match(AI_UNAVAILABLE_TEXT, /AI is unavailable right now/);
  assert.match(AI_UNAVAILABLE_TEXT, /not charged/);
});

test('dockErrorNotice: 402 upgrade_required points to the plans', () => {
  const notice = dockErrorNotice(axiosError(402, { code: 'upgrade_required', feature: 'AI Tutor', message: "You've used your 2 free AI Tutor messages for today." }));
  assert.equal(notice.kind, 'upgrade');
  assert.equal(notice.text, "You've used your 2 free AI Tutor messages for today.");
  assert.equal(notice.href, '/subscription');
});

test('dockErrorNotice: 429 token shortage links to tokens; throttles show DRF detail', () => {
  const tokens = dockErrorNotice(axiosError(429, { error: 'insufficient_tokens', message: 'Not enough tokens.', available: 0, required: 1 }));
  assert.deepEqual(tokens, { kind: 'limit', text: 'Not enough tokens.', href: '/tokens', linkLabel: 'Get tokens' });
  const throttled = dockErrorNotice(axiosError(429, { detail: 'Request was throttled. Expected available in 30 seconds.' }));
  assert.deepEqual(throttled, { kind: 'limit', text: 'Request was throttled. Expected available in 30 seconds.' });
});

test('dockErrorNotice: network failures and other errors get readable text', () => {
  assert.deepEqual(dockErrorNotice(new Error('Network Error')), { kind: 'error', text: NETWORK_ERROR_TEXT });
  assert.deepEqual(dockErrorNotice(undefined), { kind: 'error', text: NETWORK_ERROR_TEXT });
  assert.deepEqual(dockErrorNotice(axiosError(500, '<html>oops</html>')), { kind: 'error', text: GENERIC_ERROR_TEXT });
});

test('FloatingDock: notices are not replies; flashcard button only from lg', () => {
  const dock = read('src/components/FloatingDock.tsx');
  assert.doesNotMatch(dock, /Error connecting to AI/);
  assert.match(dock, /dockErrorNotice\(err\)/);
  assert.match(dock, /parseDockReply\(res\.data\)/);
  assert.match(dock, /Offline answer/);
  assert.match(dock, /aria-label="Create flashcard from selected text"\s*className="hidden lg:inline-flex/);
  // react-markdown stays out of the global bundle: the renderer is lazy.
  assert.doesNotMatch(dock, /from 'react-markdown'/);
  assert.match(dock, /dynamic\(\(\) => import\('@\/components\/FloatingDockReply'\), \{\s*ssr: false/);
  assert.match(read('src/components/FloatingDockReply.tsx'), /<ReactMarkdown skipHtml>/);
});

// ── Header / ExamSwitcher / titles ─────────────────────────────────────────

test('Header: Unlimited pill for unmetered AI, no phone logo next to the menu button', () => {
  const header = read('src/components/Header.tsx');
  assert.match(header, /import \{ isUnmeteredAi, type TokenWallet \} from '@\/hooks\/useTokenWallet'/);
  assert.match(header, /isUnmeteredAi\(tokenInfo, user\)/);
  assert.match(header, /unmeteredAi \? 'Unlimited' :/);
  assert.doesNotMatch(header, /cms-circle-logo/);
  assert.doesNotMatch(header, /'Admin' : `\$\{tokenInfo\.available\} Tokens`/);
});

test('ExamSwitcher: exam names from 380px (390px phones), codes only below', () => {
  const switcher = read('src/components/ExamSwitcher.tsx');
  assert.match(switcher, /<span className="min-\[380px\]:hidden">\{EXAM_CODES\[value\]\}<\/span>/);
  assert.match(switcher, /<span className="hidden min-\[380px\]:inline">\{EXAM_LABELS\[value\]\}<\/span>/);
  assert.doesNotMatch(switcher, /sm:hidden">\{EXAM_CODES/);
});

test('getPageTitle: /subscription matches its page heading', () => {
  assert.equal(getPageTitle('/subscription'), 'Premium Membership');
});

// ── Sidebar ────────────────────────────────────────────────────────────────

test('Sidebar: Sign Out keeps its destructive colours; no chevron beside the AI badge', () => {
  const sidebar = read('src/components/Sidebar.tsx');
  assert.match(sidebar, /className="sidebar-link w-full text-destructive hover:text-destructive hover:bg-destructive\/10/);
  assert.match(sidebar, /isActive && !showLock && !item\.badge && <ChevronRight/);
  assert.match(sidebar, /\{ href: '\/analytics', iconName: 'analytics-growth', label: 'Analytics' \}/);
});

// ── AppShell layouts (C6) ──────────────────────────────────────────────────

function pagesUnder(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(path.join(FRONTEND, dir))) {
    const rel = `${dir}/${entry}`;
    if (statSync(path.join(FRONTEND, rel)).isDirectory()) out.push(...pagesUnder(rel));
    else if (entry === 'page.tsx') out.push(rel);
  }
  return out;
}

for (const section of ['admin/import-center', 'admin/ingestion']) {
  test(`/${section}: layout uses the shared AppShell (no hand-copied shell)`, () => {
    const layout = read(`src/app/${section}/layout.tsx`);
    assert.match(layout, /import AppShell from '@\/components\/AppShell'/);
    assert.match(layout, /<AppShell>/);
    assert.doesNotMatch(layout, /import (Sidebar|Header) from/);
    assert.doesNotMatch(layout, /className="main-content"/);
    // The admin gate still runs before any admin UI renders.
    assert.match(layout, /if \(loading \|\| !isAdmin\)/);
    const pages = pagesUnder(`src/app/${section}`);
    assert.ok(pages.length >= 5, pages.join(', '));
    for (const page of pages) assert.doesNotMatch(read(page), /<Sidebar\b|<Header\b|<AppShell\b/, page);
  });
}

test('Import Center tabs: plain border-colour utilities, no `!` workaround', () => {
  const layout = read('src/app/admin/import-center/layout.tsx');
  assert.match(layout, /'border-primary text-primary'/);
  assert.doesNotMatch(layout, /border-primary!|border-transparent!/);
});

for (const route of ['analytics/dashboard_v3', 'analytics/heatmap']) {
  test(`/${route}: no nested <main>, page padding collapses inside the shell`, () => {
    const page = read(`src/app/${route}/page.tsx`);
    assert.doesNotMatch(page, /<main\b/);
    assert.match(page, /\[\.page-container_&\]:p-0/);
  });
}

test('/analytics/dashboard_v3: user-facing heading, no internal phase name', () => {
  const page = read('src/app/analytics/dashboard_v3/page.tsx');
  assert.match(page, /<h1 className="text-2xl font-semibold">Analytics Dashboard<\/h1>/);
  assert.doesNotMatch(page, /Phase 3<\/h1>/);
});

// ── globals.css cascade ────────────────────────────────────────────────────

interface CssRule { selector: string; body: string; ancestors: string[] }

/** Flat list of style rules with their enclosing at-rules (comments stripped). */
function parseCss(css: string): CssRule[] {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const rules: CssRule[] = [];
  const stack: { header: string; start: number; isAt: boolean }[] = [];
  let segmentStart = 0;
  let depth = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '{') {
      const header = text.slice(segmentStart, i).trim();
      stack.push({ header, start: i + 1, isAt: header.startsWith('@') });
      segmentStart = i + 1;
      depth += 1;
    } else if (ch === '}') {
      const open = stack.pop();
      depth -= 1;
      assert.ok(depth >= 0, `unbalanced } at offset ${i}`);
      if (open && !open.isAt) {
        rules.push({
          selector: open.header.replace(/\s+/g, ' '),
          body: text.slice(open.start, i),
          ancestors: stack.filter((s) => s.isAt).map((s) => s.header.replace(/\s+/g, ' ')),
        });
      }
      segmentStart = i + 1;
    } else if (ch === ';' && (stack.length === 0 || stack[stack.length - 1].isAt)) {
      segmentStart = i + 1;
    }
  }
  assert.equal(depth, 0, 'globals.css braces are unbalanced');
  return rules;
}

const CSS = parseCss(read('src/app/globals.css'));
const rulesFor = (selector: string) => CSS.filter((r) => r.selector.split(',').map((s) => s.trim()).includes(selector));
const inLayer = (r: CssRule, layer: string) => r.ancestors.includes(`@layer ${layer}`);
const inMedia = (r: CssRule) => r.ancestors.some((a) => a.startsWith('@media'));

test('globals.css: sidebar link visuals yield to utilities; drawer/rail overrides do not', () => {
  for (const sel of ['.sidebar-link', '.sidebar-link:hover', '.sidebar-link.active', '.sidebar-link.active::before', '.sidebar-link:focus-visible']) {
    const base = rulesFor(sel).filter((r) => !inMedia(r));
    assert.equal(base.length, 1, sel);
    assert.ok(inLayer(base[0], 'components'), `${sel} must be in @layer components`);
  }
  // Responsive overrides stay unlayered so they keep beating utilities.
  const overrides = rulesFor('.sidebar-link').filter(inMedia);
  assert.ok(overrides.length >= 2);
  for (const r of overrides) assert.ok(!r.ancestors.some((a) => a.startsWith('@layer')), r.ancestors.join(' > '));
  const railLabel = rulesFor('.sidebar .sidebar-label').filter(inMedia);
  for (const r of railLabel) assert.ok(!r.ancestors.some((a) => a.startsWith('@layer')));
});

test('globals.css: glass cards, section titles, badges and stat cards sit in @layer components', () => {
  for (const sel of ['.glass-card', '.glass-card:hover', '.glass-card::after', '.section-title', '.badge', '.badge-easy', '[data-theme="dark"] .badge-hard', '.stat-card']) {
    const rules = rulesFor(sel);
    assert.ok(rules.length > 0, sel);
    for (const r of rules) assert.ok(inLayer(r, 'components'), `${sel} rule outside @layer components`);
  }
  // The hover shimmer overlay must never swallow clicks on the card's buttons.
  const [after] = rulesFor('.glass-card::after');
  assert.match(after.body, /pointer-events:\s*none/);
});

test('globals.css: a <select class="input-field"> sizes by height, not vertical padding', () => {
  const [rule] = rulesFor('select.input-field');
  assert.ok(rule, 'select.input-field rule missing');
  assert.ok(inLayer(rule, 'components'));
  assert.match(rule.body, /padding-top:\s*0/);
  assert.match(rule.body, /padding-bottom:\s*0/);
  assert.match(rule.body, /height:\s*2\.6875rem/);
});

test('globals.css: page bottom clears the floating dock on tablets and desktops', () => {
  const reserve = CSS.filter((r) => r.selector === 'body.floating-dock-visible' && /--floating-dock-reserve/.test(r.body));
  assert.deepEqual(reserve.map((r) => r.ancestors).sort(), [['@media (min-width: 1024px)'], ['@media (min-width: 641px)']]);
  const main = rulesFor('.main-content').filter((r) => /padding-bottom/.test(r.body));
  const desktop = main.find((r) => r.ancestors.length === 0);
  const tablet = main.find((r) => r.ancestors.includes('@media (min-width: 769px) and (max-width: 1024px)'));
  assert.ok(desktop && /var\(--floating-dock-reserve/.test(desktop.body));
  assert.ok(tablet && /var\(--floating-dock-reserve/.test(tablet.body));
  // Shell-less pages (immersive practice) on tablets: room under <body>.
  const shellLess = rulesFor('body.floating-dock-visible:not(:has(.main-content))');
  assert.deepEqual(shellLess.map((r) => r.ancestors).sort(), [
    ['@media (max-width: 640px)'],
    ['@media (min-width: 641px) and (max-width: 1023px)'],
  ]);
  for (const r of shellLess) assert.match(r.body, /padding-bottom:\s*5(\.5)?rem/);
});
