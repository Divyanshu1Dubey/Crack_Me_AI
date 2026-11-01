/**
 * Wave 3b (group Z1Z5-shell-ai) — follow-ups other groups asked for:
 *  - The free-usage banner sits directly under the header bar: <Header>
 *    renders <UsageBanner> on the banner routes and PaywallRoot no longer
 *    does, so it renders exactly once (it used to sit after the footer).
 *  - UsageBanner is a rounded card like the header card, compact on phones.
 *  - The INI-CET / NEET PG practice metadata quote the lib/bankStats sizes.
 *  - paywallStore has no 'Deep Analytics' label (C14: /analytics is free).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/shell-ai-wave3b.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { USAGE_BANNER_PATHS, isUsageBannerRoute } from '../../src/lib/paywall/usageBannerRoutes.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');
const relative = (abs: string) => path.relative(FRONTEND, abs).split(path.sep).join('/');
const dropLineComments = (src: string) => src.replace(/^\s*\/\/.*$/gm, '');

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...sourceFiles(full));
    else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

// ── Free-usage banner placement ────────────────────────────────────────────

test('isUsageBannerRoute: the question banks, tests, simulator and AI tutor only', () => {
  assert.deepEqual([...USAGE_BANNER_PATHS], ['/questions', '/tests', '/simulator', '/ai-tutor']);
  for (const p of ['/questions', '/questions/neet-pg/practice', '/questions/inicet/practice',
    '/questions/practice', '/tests', '/tests/42', '/simulator', '/ai-tutor']) {
    assert.equal(isUsageBannerRoute(p), true, p);
  }
  for (const p of [null, undefined, '', '/', '/dashboard', '/subscription', '/admin',
    '/admin/questions-editor', '/analytics', '/topic-notes', '/study-time', '/tools',
    '/questions-old', '/tests-archive']) {
    assert.equal(isUsageBannerRoute(p), false, String(p));
  }
});

test('UsageBanner renders once: under the header bar, never from PaywallRoot', () => {
  const header = read('src/components/Header.tsx');
  assert.match(header, /import \{ UsageBanner \} from '@\/components\/paywall\/UsageBanner'/);
  assert.match(header, /const showUsageBanner = isUsageBannerRoute\(pathname\)/);
  // Directly after the header bar (a JSX comment may sit between), before the search dialog.
  assert.match(header, /<\/header>\s*(\{\/\*[\s\S]*?\*\/\}\s*)?\{showUsageBanner \? <UsageBanner \/> : null\}/);
  assert.ok(header.indexOf('<UsageBanner />') < header.indexOf('<SearchDialog'));

  const root = read('src/components/paywall/PaywallRoot.tsx');
  assert.doesNotMatch(root, /UsageBanner'|<UsageBanner\b|usePathname/);
  assert.match(root, /return <UpgradeModal \/>;/);
  // The modal is still mounted once, at the root layout.
  assert.equal(read('src/app/layout.tsx').match(/<PaywallRoot \/>/g)?.length, 1);

  // No other mount point anywhere under src/.
  const mounts = sourceFiles(path.join(FRONTEND, 'src'))
    .filter((f) => /<UsageBanner\b/.test(readFileSync(f, 'utf8')))
    .map(relative);
  assert.deepEqual(mounts, ['src/components/Header.tsx']);
});

test('banner routes: their Header pages show it, focus pages without a Header do not', () => {
  for (const page of [
    'src/app/questions/page.tsx',
    'src/app/questions/neet-pg/practice/page.tsx',
    'src/app/questions/inicet/practice/page.tsx',
    'src/app/tests/page.tsx',
    'src/app/simulator/page.tsx',
    'src/app/ai-tutor/page.tsx',
  ]) {
    assert.match(read(page), /<Header \/>/, page);
  }
  for (const page of ['src/app/questions/practice/page.tsx', 'src/app/tests/[id]/page.tsx']) {
    assert.doesNotMatch(read(page), /<Header\b|<AppShell\b/, page);
  }
  // AppShell pages, /subscription and admin render the Header but are no banner routes.
  for (const layout of sourceFiles(path.join(FRONTEND, 'src', 'app')).filter((f) => f.endsWith('layout.tsx'))) {
    if (!/<AppShell>/.test(readFileSync(layout, 'utf8'))) continue;
    const route = '/' + path.relative(path.join(FRONTEND, 'src', 'app'), path.dirname(layout)).split(path.sep).join('/');
    assert.equal(isUsageBannerRoute(route), false, route);
  }
});

test('UsageBanner: a rounded card like the header card, compact on phones', () => {
  const src = read('src/components/paywall/UsageBanner.tsx');
  assert.match(src, /`mb-4 w-full rounded-xl border \$\{isDepleted/);
  assert.doesNotMatch(src, /\bborder-b\b/);
  assert.doesNotMatch(src, /max-w-7xl|mx-auto/);
  assert.match(src, /className="flex items-center gap-2 px-3 py-2 text-sm sm:gap-3 sm:px-4"/);
  // Phones keep the count and the Subscribe button; the second clause and icon wait for sm.
  assert.equal(src.match(/<span className="hidden sm:inline"> /g)?.length, 2);
  assert.match(src, /className="hidden shrink-0 sm:block"/);
  assert.match(src, /href="\/subscription"/);
  // Readable in both themes.
  assert.match(src, /text-rose-900 dark:text-rose-100/);
  assert.match(src, /text-amber-900 dark:text-amber-100/);
});

// ── Practice-bank metadata ─────────────────────────────────────────────────

test('INI-CET practice metadata: the recall bank size from lib/bankStats', () => {
  const ini = dropLineComments(read('src/app/questions/inicet/practice/layout.tsx'));
  assert.match(ini, /import \{ INI_CET_QUESTION_COUNT \} from "@\/lib\/bankStats";/);
  assert.match(ini, /`Practice INI-CET recall questions \(\$\{INI_CET_QUESTION_COUNT\} in the bank\) with AI explanations, bookmarks, and spaced-repetition flashcards\. Filter by year and subject\.`/);
  assert.match(ini, /"Practice the INI-CET recall bank with AI explanations and bookmarks\."/);
  assert.match(ini, /`Practice \$\{INI_CET_QUESTION_COUNT\} INI-CET recall questions with AI explanations\.`/);
  assert.doesNotMatch(ini, /2,500\+|2018-2025|institute|full INI-CET/i);
});

test('NEET PG practice metadata: the bank size from lib/bankStats', () => {
  const neet = dropLineComments(read('src/app/questions/neet-pg/practice/layout.tsx'));
  assert.match(neet, /import \{ NEET_PG_QUESTION_COUNT \} from "@\/lib\/bankStats";/);
  assert.match(neet, /`Practice \$\{NEET_PG_QUESTION_COUNT\} NEET PG questions \(mostly exam recalls\) with AI explanations, bookmarks, and spaced-repetition flashcards\. Filter by year, subject, and topic\.`/);
  assert.match(neet, /"Practice the NEET PG question bank with /);
  assert.match(neet, /`Practice \$\{NEET_PG_QUESTION_COUNT\} NEET PG questions with AI explanations\.`/);
  assert.doesNotMatch(neet, /5,000\+|2018-2025|full NEET PG|previous-year bank/);
});

// ── C14 ────────────────────────────────────────────────────────────────────

test('paywallStore: no Deep Analytics feature label (C14)', () => {
  assert.doesNotMatch(read('src/lib/paywall/paywallStore.ts'), /deep analytics/i);
});
