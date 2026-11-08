/**
 * Jobs board (2026-11-09): only listings an admin checked against the official notification are public
 * (backend jobs/official_sources.py); the pages show and record that check.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/jobs-verified.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel: string) => readFileSync(path.join(ROOT, rel), 'utf8');

test('the API client records a verification and a rejection', () => {
    const api = read('src/lib/api.ts');
    assert.match(api, /verify: \(id: number, data: \{ source_url\?: string; approve\?: boolean \}\) => api\.post\(`\/jobs\/\$\{id\}\/verify\/`/);
    assert.match(api, /reject: \(id: number, note = ''\) => api\.post\(`\/jobs\/\$\{id\}\/reject\/`/);
});

test('the admin page creates drafts, asks for the official notification and publishes by verifying', () => {
    const page = read('src/app/admin/jobs/page.tsx');
    assert.match(page, /source_url: string;/);
    assert.match(page, /jobsAPI\.verify\(job\.id, \{ source_url: source\.trim\(\), approve: true \}\)/);
    assert.match(page, /jobsAPI\.reject\(job\.id/);
    assert.doesNotMatch(page, /appear on the candidate jobs board immediately/);
    assert.doesNotMatch(page, /job scraper/);
});

test('students see when and against what a listing was verified', () => {
    const page = read('src/app/jobs/page.tsx');
    assert.match(page, /job\.last_verified_at/);
    assert.match(page, /Official notification/);
    assert.match(page, /Always confirm the details on the official website before applying/);
});
