/**
 * Global app shell (wave 2, W11):
 *  - appShellRoutes: Header titles, FloatingDock hidden routes, exam labels
 *  - AppShell route layouts (contract C6): every wrapped route has a layout
 *    with noindex metadata, and its page renders no second Sidebar/Header
 *  - globals.css cascade: rules that used to beat Tailwind utilities from
 *    outside any @layer now live in @layer base / components
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/app-shell.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  EXAM_CODES,
  EXAM_LABELS,
  examFromPathname,
  getPageTitle,
  isExamTrack,
  isFloatingDockHiddenRoute,
} from '../../src/lib/appShellRoutes.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');

// ── Header titles ──────────────────────────────────────────────────────────

test('getPageTitle: exact routes, new shell pages and the renamed roadmap', () => {
  assert.equal(getPageTitle('/dashboard'), 'Dashboard');
  assert.equal(getPageTitle('/questions'), 'Question Bank');
  assert.equal(getPageTitle('/study-time'), 'Study Time');
  assert.equal(getPageTitle('/quests'), 'Daily Quests');
  assert.equal(getPageTitle('/mistake-notebook'), 'Mistake Notebook');
  assert.equal(getPageTitle('/practice'), 'Practice');
  assert.equal(getPageTitle('/topic-notes'), 'Topic Notes');
  assert.equal(getPageTitle('/recall/search'), 'Recall Search');
  // One name everywhere: page H1, Header title and Sidebar label.
  assert.equal(getPageTitle('/roadmap'), 'Study Roadmap');
});

test('getPageTitle: dedicated exam banks and section sub-routes', () => {
  // Used to fall back to "CrackCMS" (pageTitles matched '/questions' only).
  assert.equal(getPageTitle('/questions/neet-pg/practice'), 'NEET PG Question Bank');
  assert.equal(getPageTitle('/questions/inicet/practice'), 'INI-CET Question Bank');
  assert.equal(getPageTitle('/questions/practice'), 'Question Bank');
  assert.equal(getPageTitle('/admin/import-center/upload'), 'Import Center');
  assert.equal(getPageTitle('/admin/recall/search-analytics'), 'Recall Admin');
  assert.equal(getPageTitle('/admin/some-new-tool'), 'Admin Panel');
  assert.equal(getPageTitle('/analytics/heatmap'), 'Study Heatmap');
});

test('getPageTitle: test attempts, unknown routes and prefix boundaries', () => {
  assert.equal(getPageTitle('/tests'), 'Tests');
  assert.equal(getPageTitle('/tests/203'), 'Test');
  assert.equal(getPageTitle(null), 'CrackCMS');
  assert.equal(getPageTitle(''), 'CrackCMS');
  assert.equal(getPageTitle('/'), 'CrackCMS');
  // A section matches only on a path-segment boundary.
  assert.equal(getPageTitle('/dashboards'), 'CrackCMS');
  assert.equal(getPageTitle('/questionsx'), 'CrackCMS');
});

// ── FloatingDock ───────────────────────────────────────────────────────────

test('isFloatingDockHiddenRoute: admin tools, AI Tutor and the timed test player', () => {
  for (const p of ['/admin', '/admin/jobs', '/admin/import-center/upload', '/ai-tutor', '/tests/203', '/tests/203/review']) {
    assert.equal(isFloatingDockHiddenRoute(p), true, p);
  }
});

test('isFloatingDockHiddenRoute: study pages keep the dock', () => {
  for (const p of ['/tests', '/tests/', '/dashboard', '/questions', '/questions/neet-pg/practice', '/flashcards', '/administrator', '/ai-tutors', '/']) {
    assert.equal(isFloatingDockHiddenRoute(p), false, p);
  }
  assert.equal(isFloatingDockHiddenRoute(null), false);
  assert.equal(isFloatingDockHiddenRoute(undefined), false);
});

// ── ExamSwitcher labels ────────────────────────────────────────────────────

test('exam labels: every track has a readable label and a phone code', () => {
  assert.deepEqual(Object.keys(EXAM_CODES).sort(), Object.keys(EXAM_LABELS).sort());
  assert.equal(EXAM_LABELS.cms, 'UPSC CMS');
  assert.equal(EXAM_LABELS.neet_pg, 'NEET PG');
  assert.equal(EXAM_LABELS.ini_cet, 'INI-CET');
  for (const code of Object.values(EXAM_CODES)) assert.ok(code.length >= 3 && code.length <= 5, code);
  assert.equal(isExamTrack('neet_pg'), true);
  assert.equal(isExamTrack('toString'), false);
  assert.equal(isExamTrack(undefined), false);
});

test('examFromPathname: dedicated banks override the saved track', () => {
  assert.equal(examFromPathname('/questions/neet-pg/practice'), 'neet_pg');
  assert.equal(examFromPathname('/questions/inicet/practice'), 'ini_cet');
  assert.equal(examFromPathname('/questions'), null);
  assert.equal(examFromPathname('/questions/neet-pgx'), null);
  assert.equal(examFromPathname(null), null);
});

// ── AppShell route layouts (C6) ────────────────────────────────────────────

const SHELL_ROUTES = [
  'study-time',
  'quests',
  'mistake-notebook',
  'practice',
  'topic-notes',
  'recall/search',
  'analytics/dashboard_v3',
  'analytics/heatmap',
  'admin/announcements',
  'admin/questions-editor',
  'admin/notes',
  'admin/jobs',
  'admin/recall',
];

test('AppShell matches the per-page shell markup', () => {
  const src = read('src/components/AppShell.tsx');
  assert.match(src, /<div className="min-h-screen bg-background">\s*<Sidebar \/>\s*<div className="main-content">\s*<Header \/>\s*<div className="page-container">\{children\}<\/div>/);
});

for (const route of SHELL_ROUTES) {
  test(`/${route}: layout wraps the page in AppShell with noindex metadata`, () => {
    const layout = read(`src/app/${route}/layout.tsx`);
    assert.match(layout, /import AppShell from '@\/components\/AppShell'/);
    assert.match(layout, /<AppShell>\{children\}<\/AppShell>/);
    assert.match(layout, /export const metadata: Metadata/);
    assert.match(layout, /title: '[^']+'/);
    assert.match(layout, /robots: \{ index: false, follow: false \}/);
  });

  test(`/${route}: page renders no second Sidebar/Header`, () => {
    const page = read(`src/app/${route}/page.tsx`);
    assert.doesNotMatch(page, /<Sidebar\b|<Header\b|<AppShell\b/);
  });
}

test('/admin/recall/search-analytics: titled, shell from the parent layout only', () => {
  const layout = read('src/app/admin/recall/search-analytics/layout.tsx');
  assert.match(layout, /title: 'Recall Search Analytics'/);
  assert.doesNotMatch(layout, /AppShell/);
  assert.doesNotMatch(read('src/app/admin/recall/search-analytics/page.tsx'), /<Sidebar\b|<Header\b/);
});

test('shell pages keep a single landmark: AppShell adds no <main>', () => {
  assert.doesNotMatch(read('src/components/AppShell.tsx'), /<main\b/);
  assert.ok(existsSync(path.join(FRONTEND, 'src/app/layout.tsx')));
});

// ── globals.css cascade ────────────────────────────────────────────────────

interface CssRule { selector: string; body: string; ancestors: string[] }

/** Flat list of style rules with their enclosing at-rules (comments stripped). */
function parseCss(css: string): CssRule[] {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const rules: CssRule[] = [];
  const stack: { header: string; start: number; isAt: boolean }[] = [];
  let segmentStart = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '{') {
      const header = text.slice(segmentStart, i).trim();
      stack.push({ header, start: i + 1, isAt: header.startsWith('@') });
      segmentStart = i + 1;
    } else if (ch === '}') {
      const open = stack.pop();
      if (open && !open.isAt) {
        rules.push({
          selector: open.header.replace(/\s+/g, ' '),
          body: text.slice(open.start, i),
          ancestors: stack.filter((s) => s.isAt).map((s) => s.header.replace(/\s+/g, ' ')),
        });
      }
      segmentStart = i + 1;
    } else if (ch === ';' && (stack.length === 0 || stack[stack.length - 1].isAt)) {
      segmentStart = i + 1; // statement at-rules (@import, @custom-variant ...)
    }
  }
  return rules;
}

const CSS = parseCss(read('src/app/globals.css'));
const rulesFor = (selector: string) => CSS.filter((r) => r.selector.split(',').map((s) => s.trim()).includes(selector));
const inLayer = (r: CssRule, layer: string) => r.ancestors.includes(`@layer ${layer}`);

test('globals.css: default border colour sits in @layer base (utilities win)', () => {
  const star = CSS.filter((r) => r.selector === '*' && /border-color:\s*var\(--color-border\)/.test(r.body));
  assert.equal(star.length, 1);
  assert.ok(inLayer(star[0], 'base'), 'the * border-color rule must be in @layer base');
});

test('globals.css: element defaults (max-width cap, headings) sit in @layer base', () => {
  for (const sel of ['main', 'h2']) {
    const rules = rulesFor(sel);
    assert.ok(rules.length > 0, sel);
    for (const r of rules) assert.ok(inLayer(r, 'base'), `${sel} rule outside @layer base`);
  }
});

test('globals.css: prose, buttons and inputs sit in @layer components', () => {
  for (const sel of ['.legal-content a', '.legal-content p', '.btn-primary', '.btn-secondary', '.input-field', '.input-field:focus']) {
    const rules = rulesFor(sel);
    assert.ok(rules.length > 0, sel);
    for (const r of rules) assert.ok(inLayer(r, 'components'), `${sel} rule outside @layer components`);
  }
});

test('globals.css: .btn-secondary lays its icon and label out in a row', () => {
  const [rule] = rulesFor('.btn-secondary');
  assert.match(rule.body, /display:\s*inline-flex/);
  assert.match(rule.body, /align-items:\s*center/);
});

test('globals.css: one .gradient-text definition (plus its dark variant)', () => {
  assert.equal(rulesFor('.gradient-text').length, 1);
  assert.equal(rulesFor('[data-theme="dark"] .gradient-text').length, 1);
  assert.doesNotMatch(read('src/app/globals.css'), /@keyframes gradientShift/);
});

test('globals.css: .main-content has no layout containment (fixed overlays cover the viewport)', () => {
  for (const r of rulesFor('.main-content')) {
    assert.doesNotMatch(r.body, /contain:[^;]*\blayout\b/);
  }
});

test('globals.css: collapsed desktop sidebar keeps the page gutter; tablet rail never hides', () => {
  const hidden = rulesFor('body.sidebar-hidden .main-content');
  assert.equal(hidden.length, 1);
  assert.doesNotMatch(hidden[0].body, /padding/);
  assert.deepEqual(hidden[0].ancestors, ['@media (min-width: 1025px)']);
  const desktopHidden = rulesFor('.sidebar.desktop-hidden');
  assert.equal(desktopHidden.length, 1);
  assert.deepEqual(desktopHidden[0].ancestors, ['@media (min-width: 1025px)']);
});

test('globals.css: floating-dock space is reserved once, never on nested <main>s', () => {
  const dockRules = CSS.filter((r) => r.selector.includes('floating-dock-visible'));
  assert.ok(dockRules.length > 0);
  for (const r of dockRules) {
    assert.doesNotMatch(r.selector, /floating-dock-visible\s+(main|\.main-content)\b/, r.selector);
  }
});

test('globals.css: hamburger visibility and header reserve agree at 768px', () => {
  const header = read('src/components/Header.tsx');
  // .mobile-menu-btn shows at max-width 768px, so the header keeps its
  // reserve and hides the title until 769px (Tailwind md starts at 768px).
  assert.ok(CSS.some((r) => r.selector === '.mobile-menu-btn' && r.ancestors.includes('@media (max-width: 768px)') && /display:\s*flex/.test(r.body)));
  assert.match(header, /\bpl-10\b[^"`]*\bmin-\[769px\]:pl-0\b/);
  assert.doesNotMatch(header, /\bmd:pl-0\b|\bhidden md:block\b/);
});
