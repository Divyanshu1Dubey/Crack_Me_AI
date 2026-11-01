/**
 * Upload + Import Center pages, wave 3 (Z8, for the Z1 shell requests, C6):
 *  - /upload renders the signed-in chrome (Sidebar + Header) exactly once,
 *    with no AppShell in its layout and no nested <main> (the root layout
 *    already renders <main id="main-content">)
 *  - Import Center overlays still portal to <body>, without the stale
 *    "`.main-content` has `contain: layout`" rationale
 *  - Import Center upload CTA is right-aligned again: the FloatingDock it
 *    used to dodge on phones is hidden on /admin/**
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/imports-wave3.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { isFloatingDockHiddenRoute } from '../../src/lib/appShellRoutes.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');
const withoutBlockComments = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '');

test('/upload: Sidebar + Header chrome, no nested <main>', () => {
  const page = read('src/app/upload/page.tsx');
  assert.match(page, /import Sidebar from '@\/components\/Sidebar'/);
  assert.match(page, /import Header from '@\/components\/Header'/);
  assert.match(page, /<div className="main-content">\s*<Header \/>/);
  assert.doesNotMatch(withoutBlockComments(page), /<main\b|<\/main>/);
  assert.match(read('src/app/layout.tsx'), /<main id="main-content">/);
  // Exactly one shell: the page renders it once, and its layout adds none.
  assert.equal(page.match(/<Sidebar \/>/g)?.length, 1);
  assert.equal(page.match(/<Header \/>/g)?.length, 1);
  assert.doesNotMatch(
    read('src/app/upload/layout.tsx'),
    /import (AppShell|Sidebar|Header) from|<(AppShell|Sidebar|Header)\b|className="main-content"/,
  );
});

test('Import Center overlays portal to <body> without the stale containment rationale', () => {
  for (const rel of [
    'src/app/admin/import-center/review/page.tsx',
    'src/app/admin/import-center/batches/[id]/page.tsx',
  ]) {
    const page = read(rel);
    assert.match(page, /\/\/ Portal to <body>:[\s\S]{0,300}return createPortal\(/, rel);
    assert.doesNotMatch(page, /\.main-content has `contain: layout`/, rel);
  }
});

test('Import Center upload CTA: right-aligned, no FloatingDock workaround on /admin', () => {
  assert.equal(isFloatingDockHiddenRoute('/admin/import-center/upload'), true);
  const page = read('src/app/admin/import-center/upload/page.tsx');
  assert.match(page, /<div className="flex justify-end gap-2">\s*<button/);
  assert.doesNotMatch(page, /justify-start gap-2 sm:justify-end|clear of the floating Ask AI/);
});
