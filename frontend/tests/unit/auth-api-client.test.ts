/**
 * Unit tests for src/lib/api.ts request helpers (no network: a capturing
 * axios adapter answers every request).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/auth-api-client.test.ts
 *
 * C9   platform-wide admin system actions send exactly what the caller gave
 *      (no automatic confirm phrase), so the server's typed-phrase check runs
 * C11  questionsAPI.getYears passes exam_type / exam_source
 * EXT  extractionItemPublish sends the exam_type body
 * W2   Django's own 500 / DEBUG pages are not reported as a gateway timeout
 * W3b  ingestionAPI.jobCounts reads the per-status job counts
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

process.env.NEXT_PUBLIC_AUTH_MODE = 'local'; // no Supabase client in this test

const mod = await import('../../src/lib/api.ts');
const api = mod.default;
const { authAPI, questionsAPI, ingestionAPI, extractApiErrorMessage } = mod;

type Captured = { url?: string; method?: string; data?: unknown; params?: unknown };
let captured: Captured[] = [];

beforeEach(() => {
  captured = [];
  api.defaults.adapter = async (config) => {
    captured.push({ url: config.url, method: config.method, data: config.data, params: config.params });
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
  };
});

const body = (entry: Captured) => (typeof entry.data === 'string' ? JSON.parse(entry.data) : entry.data ?? {});

test('C9: scope "all" is sent without a default confirm phrase', async () => {
  await authAPI.adminResetAttempts({ scope: 'all' });
  await authAPI.adminClearAnalytics({ scope: 'all' });
  await authAPI.adminRerunEvaluation({ scope: 'all' });
  assert.equal(captured.length, 3);
  for (const entry of captured) assert.deepEqual(body(entry), { scope: 'all' }, entry.url);

  captured = [];
  await authAPI.adminResetAttempts({ scope: 'all', confirm: 'RESET ALL' });
  assert.deepEqual(body(captured[0]), { scope: 'all', confirm: 'RESET ALL' });
});

test('C11: getYears forwards the exam filters', async () => {
  await questionsAPI.getYears({ exam_type: 'neet_pg' });
  await questionsAPI.getYears();
  assert.equal(captured[0].url, '/questions/years/');
  assert.deepEqual(captured[0].params, { exam_type: 'neet_pg' });
  assert.equal(captured[1].params, undefined);
});

test('W3b: ingestionAPI.jobCounts GETs the per-status counts', async () => {
  await ingestionAPI.jobCounts();
  assert.equal(captured.length, 1);
  assert.equal(captured[0].url, '/ingestion/jobs/counts/');
  assert.equal(captured[0].method, 'get');
});

test('extractionItemPublish sends exam_type', async () => {
  await questionsAPI.extractionItemPublish(7, { exam_type: 'inicet' });
  await questionsAPI.extractionItemPublish(8);
  assert.equal(captured[0].url, '/questions/extraction/items/7/publish/');
  assert.deepEqual(body(captured[0]), { exam_type: 'inicet' });
  assert.deepEqual(body(captured[1]), {});
});

test("Django's DEBUG / 500 pages are server errors, not a gateway timeout", () => {
  const debugPage = '<!DOCTYPE html><html><head><title>KeyError at /api/x/</title></head><body>'
    + "You're seeing this error because you have <code>DEBUG = True</code></body></html>";
  assert.equal(extractApiErrorMessage(debugPage), 'Something went wrong on our server. Please try again.');
  assert.equal(
    extractApiErrorMessage('\n<!doctype html>\n<html lang="en">\n<head><title>Server Error (500)</title></head>\n<body><h1>Server Error (500)</h1></body></html>'),
    'Something went wrong on our server. Please try again.',
  );
  assert.equal(
    extractApiErrorMessage('<!DOCTYPE html><html><head><title>OperationalError at /api/q/</title></head><body>DEBUG = True</body></html>'),
    'Server database is not ready. Please try again in a minute.',
  );
  // A real gateway page is still a gateway timeout.
  assert.match(extractApiErrorMessage('<html><body><h1>504 Gateway Timeout</h1></body></html>'), /gateway timeout/);
  // JSON payloads are unchanged.
  assert.equal(extractApiErrorMessage({ error: 'Nope' }), 'Nope');
});
