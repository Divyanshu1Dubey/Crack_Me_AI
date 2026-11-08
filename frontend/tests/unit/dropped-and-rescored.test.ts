/**
 * Questions UPSC dropped (shown, never scored) and re-scored attempts (2026-11-09): the score formatter and the
 * wiring of the badge / notes on the student pages. Scoring itself is the backend's (tests_engine/scoring.py).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/dropped-and-rescored.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { formatMarks } from '../../src/lib/scoreFormat.ts';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel: string) => readFileSync(path.join(ROOT, rel), 'utf8');

test('scores read at most two decimals', () => {
    assert.equal(formatMarks(0.33999999999999997), '0.34');
    assert.equal(formatMarks(2), '2');
    assert.equal(formatMarks(1.6699999999999999), '1.67');
    assert.equal(formatMarks(-0.001), '0');
    assert.equal(formatMarks('3'), '3');
    assert.equal(formatMarks(null), '–');
    assert.equal(formatMarks(undefined), '–');
    assert.equal(formatMarks('abc'), '–');
});

test('every student view of a question shows the "Dropped by UPSC" badge', () => {
    for (const file of ['src/app/tests/[id]/page.tsx', 'src/app/practice/page.tsx',
        'src/app/questions/practice/page.tsx', 'src/components/question/ExamQuestionBank.tsx']) {
        const source = read(file);
        assert.match(source, /import DroppedByUpscBadge from ["']@\/components\/question\/DroppedByUpscBadge["']/, file);
        assert.match(source, /dropped_by_upsc\s*(&&|\?)\s*<DroppedByUpscBadge/, file);
    }
});

test('the test result and review say what was not scored and what was re-scored', () => {
    const page = read('src/app/tests/[id]/page.tsx');
    assert.match(page, /result\.not_scored_count/);
    assert.match(page, /result\.rescored_at/);
    assert.match(page, /formatMarks\(result\.original_score\)/);
    assert.match(page, /rd\?\.not_scored\s*\n?\s*\?/);
    assert.match(page, /Score: \{formatMarks\(result\.score\)\} \/ \{formatMarks\(result\.total_marks\)\}/);
});
