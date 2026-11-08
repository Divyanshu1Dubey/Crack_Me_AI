/**
 * AI explanation batch (2026-11-09): the admin page, its API client and the student label. Generation and its
 * checks are the backend's (questions/explanation_batch.py).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/explanation-batch.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel: string) => readFileSync(path.join(ROOT, rel), 'utf8');

test('the API client reaches the batch and review-queue endpoints', () => {
    const api = read('src/lib/editorialAPI.ts');
    for (const route of ['/questions/explanation-batches/', '/questions/explanation-batches/${runId}/process/',
        '/questions/explanation-batches/${runId}/items/', '/questions/explanation-review/']) {
        assert.ok(api.includes(route), route);
    }
});

test('the admin page is linked, shelled and reviews through the editorial endpoint', () => {
    assert.match(read('src/components/Sidebar.tsx'), /href: '\/admin\/explanations', label: 'AI Explanations'/);
    assert.match(read('src/lib/appShellRoutes.ts'), /'\/admin\/explanations': 'AI Explanations'/);
    assert.match(read('src/app/admin/explanations/layout.tsx'), /<AppShell>/);
    const page = read('src/app/admin/explanations/page.tsx');
    assert.match(page, /editorialAPI\.reviewExplanation\(questionId\)/);
    assert.match(page, /explanationBatchAPI\.process\(runId/);
    assert.match(page, /\[\.page-container_&\]:p-0/);
    assert.doesNotMatch(page, /<main\b/);
});

test('students see that an explanation is AI-generated and not reviewed yet', () => {
    const bank = read('src/components/question/ExamQuestionBank.tsx');
    assert.match(bank, /detail\.explanation_status === 'ai_generated'/);
    assert.match(bank, /AI-generated, not yet reviewed by our team/);
});
