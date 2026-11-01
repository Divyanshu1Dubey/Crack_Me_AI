// Regression tests for the shared exam-pattern constant and the public tools
// (PUB-05, PUB-11, PUB-12, PUB-27, PUB-37, PUB-07).
// Run: node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const ep = await import('../../src/lib/examPatterns.ts');
const { analyzePyqAttempts } = await import('../../src/app/tools/pyq-attempt-analyzer/analyze.ts');
const rank = await import('../../src/app/tools/category-rank-filter/rankModel.ts');
const cutoff = await import('../../src/app/tools/cutoff-analyzer/cutoffModel.ts');
const weight = await import('../../src/app/tools/subject-weightage-analyzer/weightage.ts');
const plans = await import('../../src/app/subscription/plans.ts');

test('UPSC CMS pattern matches the notice: 2 x 120 Qs, 250 marks each, 500 + 100 = 600', () => {
    const p = ep.UPSC_CMS_PATTERN;
    assert.equal(p.papers.length, 2);
    for (const paper of p.papers) {
        assert.equal(paper.questions, 120);
        assert.equal(paper.marks, 250);
        assert.equal(paper.durationMinutes, 120);
        assert.equal(paper.subjects.reduce((a, s) => a + s.questions, 0), paper.questions, `${paper.name} subject split sums to 120`);
    }
    assert.equal(p.totalQuestions, 240);
    assert.equal(p.writtenMarks, 500);
    assert.equal(p.personalityTestMarks, 100);
    assert.equal(p.totalMarks, 600);
    assert.match(p.mode, /Computer-Based/);
});

test('CMS marking: +2.08 per correct, one-third (0.69) per wrong', () => {
    assert.equal(ep.round2(ep.CMS_MARKS_PER_QUESTION), 2.08);
    assert.equal(ep.round2(ep.CMS_PENALTY_PER_WRONG), 0.69);
    assert.equal(ep.CMS_MARKING_LABEL, '+2.08 / −0.69');
    const s = ep.scoreCmsAttempt({ correct: 18, incorrect: 5 });
    assert.equal(s.correctMarks, 37.5);
    assert.equal(s.penalty, 3.47);
    assert.equal(s.score, 34.03);
    // A full paper is worth exactly 250; three wrong answers cancel one right one.
    assert.equal(ep.cmsMaxMarks(120), 250);
    assert.equal(ep.scoreCmsAttempt({ correct: 1, incorrect: 3 }).score, 0);
    assert.equal(ep.scoreCmsAttempt({ correct: -4, incorrect: Number.NaN }).score, 0);
});

test('concluded exam dates are hidden from the countdown', () => {
    const dates = [
        { name: 'Past', date: '2026-08-02', href: '/cms' },
        { name: 'Later', date: '2027-08-01', href: '/cms' },
        { name: 'Sooner', date: '2027-03-01', href: '/neet-pg' },
    ];
    const upcoming = ep.upcomingExamDates(new Date('2026-11-01T10:00:00'), dates);
    assert.deepEqual(upcoming.map((d) => d.name), ['Sooner', 'Later']);
    // exam day itself still counts as upcoming
    assert.equal(ep.upcomingExamDates(new Date('2026-08-02T15:00:00'), dates)[0].name, 'Past');
    // with the shipped config (2026 dates) nothing is upcoming in Nov 2026
    assert.equal(ep.upcomingExamDates(new Date('2026-11-01T10:00:00')).length, 0);
});

test('PYQ attempt accuracy = sum(correct) / sum(total), not / number of lines', () => {
    const r = analyzePyqAttempts('Cardiology, 8, 10\nNeurology, 6, 8\nSurgery, 5, 7\nOBG, 9, 10');
    assert.equal(r.totalCorrect, 28);
    assert.equal(r.totalQuestions, 35);
    assert.equal(r.accuracy, 80);
    assert.ok(r.accuracy <= 100);
    assert.deepEqual(r.mastered.sort(), ['Cardiology', 'Neurology', 'OBG'].sort());
    const bad = analyzePyqAttempts('Topic only\nX, 12, 10\nY, 1, 0');
    assert.equal(bad.skippedLines, 2);
    assert.equal(bad.accuracy, 100, 'correct is clamped to total (10/10)');
});

test('Category Rank Filter: General is the open pool, EWS exists, rank 1 is not "Very Low"', () => {
    const ids = rank.CATEGORIES.map((c) => c.id);
    assert.ok(ids.includes('ews'));
    const general = rank.categoryInfo('general');
    assert.equal(general.vacancyPct, 40.5);
    assert.ok(rank.categoryVacancies('general') > 0);
    assert.equal(rank.TOTAL_VACANCIES, ep.UPSC_CMS_CYCLE.vacancies);
    assert.equal(rank.computeRankAnalysis(1, 'general', 'general').selectionChance, 'Very High');
    for (const c of ids) {
        const r = rank.computeRankAnalysis(50, 'general', c);
        assert.ok(Number.isFinite(r.categoryRank / r.vacancies), `${c} ratio is finite`);
    }
});

test('Cutoff analyzer uses the cutoff pages data on the 500-mark scale', () => {
    const data = cutoff.historicalCutoffs();
    assert.equal(cutoff.CUTOFF_MAX_MARKS, 500);
    for (const [cat, byYear] of Object.entries(data)) {
        for (const v of Object.values(byYear)) {
            assert.ok(v > 150 && v <= 500, `${cat} cutoff ${v} is on the 500 scale`);
        }
    }
    assert.ok(cutoff.trendCategories(data).includes('General'));
    const { confidence } = cutoff.linearRegressionPredict([280, 295, 305]);
    assert.equal(confidence, 'low', 'three approximate points never give a confident forecast');
    assert.match(cutoff.scoreAdvice(340, 310), /above/);
    assert.match(cutoff.scoreAdvice(250, 310), /below/);
});

test('Subject weightage = official split (adds up to 100%), bank codes fold into CMS subjects', () => {
    const rows = weight.officialCmsWeightage();
    assert.equal(rows.length, 5);
    assert.equal(rows.reduce((a, r) => a + r.questions, 0), 240);
    assert.ok(Math.abs(rows.reduce((a, r) => a + r.sharePct, 0) - 100) < 0.2);
    assert.equal(rows.find((r) => r.subject === 'General Medicine').sharePct, 40);
    const counts = weight.bankCountsByCmsSubject([
        { code: 'MED', count: 756 }, { code: 'DER', count: 18 }, { code: 'PSY', count: 3 },
        { code: 'SUR', count: 277 }, { code: 'ENT', count: 9 }, { code: 'IMPORTED', count: 339 },
    ]);
    assert.equal(counts['General Medicine'], 777);
    assert.equal(counts.Surgery, 286);
    assert.equal(Object.keys(counts).length, 2);
});

test('plans.ts matches what the backend sells (PLAN_FEATURES prices, PURCHASABLE_PLANS)', () => {
    const backend = fileURLToPath(new URL('../../../backend/accounts/', import.meta.url));
    const models = readFileSync(`${backend}models.py`, 'utf8');
    const views = readFileSync(`${backend}views.py`, 'utf8');
    const purchasable = views.match(/PURCHASABLE_PLANS = frozenset\(\{([^}]*)\}\)/)[1];
    for (const plan of plans.PREMIUM_PLANS) {
        assert.ok(purchasable.includes(`'${plan.id}'`), `${plan.id} is purchasable`);
        const block = models.slice(models.indexOf(`'${plan.id}': {`));
        const price = Number(block.match(/'price_inr': Decimal\('([\d.]+)'\)/)[1]);
        assert.equal(plan.priceInr, price, `${plan.id} price`);
        const unlimited = /'unlimited_ai': True/.test(block.slice(0, block.indexOf('},')));
        assert.equal(plan.unlimitedAi, unlimited, `${plan.id} unlimited_ai`);
    }
    assert.ok(!purchasable.includes("'legacy'"), 'the Rs 199 legacy pass is not sold');
    assert.equal(plans.LOWEST_PLAN_PRICE_INR, 129);
    assert.equal(plans.premiumAggregateOffer().lowPrice, '129');
});
