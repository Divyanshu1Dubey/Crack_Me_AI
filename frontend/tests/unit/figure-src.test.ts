/**
 * Question figures load from the image endpoint, never from retired Supabase Storage (2026-11-04):
 * src/lib/figureSrc.ts, src/lib/imageTokens.ts and the pages that show figures.
 *
 * Live symptom: /questions?q=25471 showed two broken figures and "[image unavailable: image #6991]":
 * the question view handed the browser the stored Supabase address (host shut down 2026-11-03) while
 * the image endpoint served both figures.
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/figure-src.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { apiUrl } from '../../src/lib/apiBase.ts';
import {
    figureRetryUrl,
    figureServeUrl,
    figureSrc,
    inlineFigureIds,
    isRetiredStorageUrl,
    sidePaneFigures,
} from '../../src/lib/figureSrc.ts';
import { clearImageTokenCache, resolveImageTokens } from '../../src/lib/imageTokens.ts';

const RETIRED = 'https://ryuvcdthjnxyetdyjbph.supabase.co/storage/v1/object/public/'
    + 'crack-cms-question-images/question_images/25471/5f4264f72ea73c5b.png';
const SERVE = (id: number) => apiUrl(`/questions/images/${id}/serve/`);

test('retired storage addresses are recognised, nothing else', () => {
    assert.equal(isRetiredStorageUrl(RETIRED), true);
    assert.equal(isRetiredStorageUrl('  HTTPS://abc.SUPABASE.co/storage/v1/object/public/x.png'), true);
    for (const url of ['', null, undefined, '/media/recall_images/x.png', 'https://cdn.example.test/x.png',
        'https://supabase.co.example.test/storage/x.png', 'https://abc.supabase.co/rest/v1/x']) {
        assert.equal(isRetiredStorageUrl(url), false, String(url));
    }
});

test('a figure loads from the image endpoint unless the API gave a live address', () => {
    assert.equal(figureServeUrl(6991), SERVE(6991));
    // The live symptom: the stored Supabase address of an admin upload.
    assert.equal(figureSrc({ id: 6991, url: RETIRED }), SERVE(6991));
    assert.equal(figureSrc({ id: '6992', url: RETIRED }), SERVE(6992));
    // Empty, or a /media/ path (served only by a development server): the endpoint too.
    assert.equal(figureSrc({ id: 7, url: '' }), SERVE(7));
    assert.equal(figureSrc({ id: 8, file: '/media/recall_images/a.png' }), SERVE(8));
    assert.equal(figureSrc({ id: 9, file_url: 'https://api.cracklabs.app/media/question_images/b.png' }), SERVE(9));
    // What the API gives otherwise stays: the endpoint (signed or not), another live host.
    const signed = 'https://api.cracklabs.app/api/questions/images/10/serve/?t=abc';
    assert.equal(figureSrc({ id: 10, url: signed }), signed);
    assert.equal(figureSrc({ id: 11, url: 'https://cdn.example.test/fig.png' }), 'https://cdn.example.test/fig.png');
    // serve_url (admin image rows) comes first.
    assert.equal(figureSrc({ id: 12, serve_url: signed, url: RETIRED }), signed);
    // The backend's relative fallback belongs to the API host.
    assert.equal(figureSrc({ id: 13, url: '/api/questions/images/13/serve/?t=x' }),
        apiUrl('/questions/images/13/serve/?t=x'));
    // Without an id there is nothing better to load.
    assert.equal(figureSrc({ url: RETIRED }), RETIRED);
    assert.equal(figureSrc(null), '');
});

test('a failed figure is retried once at a distinct address', () => {
    assert.equal(figureRetryUrl(SERVE(1)), `${SERVE(1)}?retry=1`);
    assert.equal(figureRetryUrl(`${SERVE(1)}?t=abc`), `${SERVE(1)}?t=abc&retry=1`);
    assert.equal(figureRetryUrl('data:image/png;base64,AAAA'), 'data:image/png;base64,AAAA');
    assert.equal(figureRetryUrl(''), '');
});

test('a figure the stem shows inline is not repeated in the side pane', () => {
    const stem = 'Given below is a table [[img:6991]] [[img:6992]]. Consider the following statements.';
    assert.deepEqual([...inlineFigureIds(stem)], [6991, 6992]);
    const figures = [{ id: 6991 }, { id: 6992 }, { id: 7000 }];
    assert.deepEqual(sidePaneFigures(figures, stem), [{ id: 7000 }]);
    assert.deepEqual(sidePaneFigures(figures, 'No tokens here'), figures);
    assert.deepEqual(sidePaneFigures(null, stem), []);
});

test('practice-page tokens resolve to the image endpoint, not the stored address', () => {
    clearImageTokenCache();
    const html = resolveImageTokens('Table: [[img:6991]]', [{ id: 6991, url: RETIRED }], 'figure-src-test');
    assert.ok(html.includes(`<img src="${SERVE(6991)}"`), html);
    assert.doesNotMatch(html, /supabase/);
});

test('every question-figure surface goes through figureSrc', () => {
    const files = [
        'src/components/FormattedText.tsx',
        'src/components/question/ExamQuestionBank.tsx',
        'src/app/tests/[id]/page.tsx',
        'src/components/ai/RelatedFigures.tsx',
        'src/app/admin/questions-editor/QuestionEditModal.tsx',
        'src/lib/imageTokens.ts',
    ];
    for (const file of files) {
        const source = readFileSync(file, 'utf8');
        assert.match(source, /figureSrc\(/, file);
        assert.doesNotMatch(source, /img\.(url|file_url) \|\| img\.(file|file_url|url)\b/, file);
    }
    const bank = readFileSync('src/components/question/ExamQuestionBank.tsx', 'utf8');
    assert.match(bank, /sidePaneFigures\(stemFigures, detail\?\.question_text\)/);
    // The zoom viewer opens the side pane's figures, so the pane's index opens the same figure.
    assert.match(bank, /images=\{\(paneFigures as ViewerImage\[\]\)/);
    // Failed figures: retried, then a placeholder (not the browser's broken-image icon).
    const formatted = readFileSync('src/components/FormattedText.tsx', 'utf8');
    assert.match(formatted, /<FigureImage/);
});
