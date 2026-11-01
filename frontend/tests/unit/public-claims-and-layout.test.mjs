// Regression tests for the wave-2 public-site fixes: one data-backed bank
// figure everywhere, honest INI-CET / FMGE / USMLE / gov-jobs copy, the
// /neet-pg subject grid and year tiles, the shared public nav, blog CTAs,
// links and reviewers, CMS marking in blog posts, the CMS service predictor,
// PostHog re-opt-in, consent copy, and the generated brand icons.
// Run (from frontend/): node --import ./tests/unit/register-ts-alias.mjs --test "tests/unit/*.test.mjs"
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel) => readFileSync(path.join(FRONTEND, rel), 'utf8');

const bank = await import('../../src/lib/bankStats.ts');
const seo = await import('../../src/lib/seo.ts');
const meta = await import('../../src/lib/metadata.ts');
const blog = await import('../../src/lib/blog.ts');
const ep = await import('../../src/lib/examPatterns.ts');
const neet = await import('../../src/components/neet-pg/neetPgLandingData.ts');
const nav = await import('../../src/components/publicNavRoutes.ts');
const toc = await import('../../src/components/blogToc.ts');
const predictor = await import('../../src/app/tools/college-predictor/servicePredictor.ts');
const { posthogLoaderScript, RELAYED_EVENTS } = await import('../../src/lib/analytics.ts');

function walk(dir) {
    if (!existsSync(dir)) return [];
    return readdirSync(dir).flatMap((name) => {
        const p = path.join(dir, name);
        return statSync(p).isDirectory() ? walk(p) : [p];
    });
}

// Public/marketing sources this group owns (other groups' files are checked by their own tests).
const PUBLIC_SOURCES = [
    ...['about', 'cms', 'exams', 'neet-pg', 'ini-cet', 'fmge', 'usmle', 'guides', 'tools', 'blog',
        'government-doctor-jobs', 'medical-officer', 'resources', 'privacy-policy', 'terms', 'cookie-policy', '_landing',
        'ai-attribution-policy', 'editorial-policy', 'medical-review-policy', 'disclaimer', 'refund-policy']
        .flatMap((d) => walk(path.join(FRONTEND, 'src/app', d))),
    ...['src/app/page.tsx', 'src/app/layout.tsx'].map((f) => path.join(FRONTEND, f)),
    ...['ExamLandingLayout.tsx', 'GuideLayout.tsx', 'ComparisonLayout.tsx', 'Footer.tsx', 'BlogPostLayout.tsx',
        'LegalLayout.tsx', 'CutoffLayout.tsx', 'PublicNav.tsx', 'neet-pg/NeetPgLanding.tsx', 'exams/ExamMicrosite.tsx',
        'ui/MagicBento.tsx'].map((f) => path.join(FRONTEND, 'src/components', f)),
    ...walk(path.join(FRONTEND, 'src/lib')),
    ...walk(path.join(FRONTEND, 'src/content')),
    ...['llms.txt', 'llms-full.txt', 'manifest.json', 'site.webmanifest'].map((f) => path.join(FRONTEND, 'public', f)),
].filter((f) => /\.(tsx?|txt|json|webmanifest)$/.test(f));

// Bank claims the data does not support (prod: 1,880 active dated CMS PYQs,
// ~4,200 NEET PG, ~100 INI-CET; no FMGE/USMLE bank).
const INFLATED = [
    /\b2,000\+\s*(UPSC|PYQ|previous|Verified|year-wise)/i,
    /\b2000\+\s*(active|Verified|PYQ)/i,
    /\b(2,300|1,920|3,300|12,000|18,000|8,000)\+/,
    /\b10,000\+\s*(USMLE|PYQ)/i,
    /\b6,000\+\s*(PYQ|MO)/i,
    /\b1,200\+\s*(PYQ|NEET)/i,
    // A bank size claimed for 2009–2024 (UPSC's own "Question Papers
    // (2009–2024)" archive label is a legitimate reference).
    /\d,\d{3}\+[^.\n]{0,60}2009[-–]2024/,
    /'2000\+'/,
];

test('bank figures: one shared constant, rounded down from the production bank', () => {
    assert.equal(bank.CMS_PYQ_COUNT, '1,800+');
    assert.equal(bank.CMS_PYQ_YEARS, '2018–2025');
    assert.equal(bank.CMS_PYQ_YEAR_COUNT, 8);
    assert.equal(bank.NEET_PG_QUESTION_COUNT, '4,000+');
    assert.equal(bank.INI_CET_QUESTION_COUNT, 'about 100');
    assert.equal(bank.INI_CET_BANK_HREF, '/questions/inicet/practice');
    assert.ok(seo.siteDescription.includes(bank.CMS_PYQ_PHRASE), 'meta description uses the constant');
    assert.ok(meta.orgSchema().description.includes(bank.CMS_PYQ_COUNT), 'Organization JSON-LD uses the constant');
});

test('no public page, data file or static text repeats an inflated bank size', () => {
    assert.ok(PUBLIC_SOURCES.length > 150, `scanned ${PUBLIC_SOURCES.length} files`);
    const offenders = [];
    for (const file of PUBLIC_SOURCES) {
        if (!existsSync(file)) continue;
        const text = readFileSync(file, 'utf8');
        for (const re of INFLATED) {
            const m = text.match(re);
            if (m) offenders.push(`${path.relative(FRONTEND, file)}: "${m[0]}"`);
        }
    }
    assert.deepEqual(offenders, []);
    // Static files carry the same figure as the constant.
    for (const f of ['public/llms.txt', 'public/manifest.json', 'public/site.webmanifest']) {
        assert.ok(read(f).includes(bank.CMS_PYQ_COUNT), `${f} states ${bank.CMS_PYQ_COUNT}`);
    }
});

test('/ini-cet links the real INI-CET bank and states its size; no FMGE/USMLE bank claims', () => {
    const iniCet = read('src/app/ini-cet/page.tsx');
    assert.match(iniCet, /pyqHref: INI_CET_BANK_HREF/);
    assert.match(iniCet, /INI_CET_QUESTION_COUNT/);
    assert.doesNotMatch(iniCet, /not live yet/);
    const usmle = read('src/app/usmle/page.tsx');
    assert.match(usmle, /pyqHref: null/);
    assert.doesNotMatch(usmle, /numeric score|Every CrackCMS USMLE question|emoji: '🇺🇸'/);
    assert.match(usmle, /Pass\/Fail only \(since 26 January 2022\)/);
    assert.doesNotMatch(read('src/app/guides/usmle-step-1-guide/page.tsx'), /USMLE Step 1 MCQs aligned/);
    assert.doesNotMatch(read('src/app/guides/ini-cet-complete-guide/page.tsx'), /rank prediction|1,000\+ curated/);
    assert.doesNotMatch(read('src/app/government-doctor-jobs/page.tsx'), /number: '500\+'|number: '28 states'|state-specific mocks/);
    assert.match(read('src/app/fmge/page.tsx'), /label: 'Age \/ time limit'/);
});

test('/neet-pg grid: NEET PG subjects with questions, biggest first; no placeholder buckets', () => {
    const rows = neet.pgSubjectsFromStats([
        { id: 1, name: 'Anatomy', code: 'ANA', count: 0, solved: 0 },
        { id: 2, name: 'Radiodiagnosis', code: 'RAD', count: 617, solved: 0 },
        { id: 3, name: 'Expert Curated', code: 'IMPORTED', count: 40, solved: 0 },
        { id: 4, name: 'Pharmacology', code: 'PHM', count: 449, solved: 2 },
        { id: 5, name: 'ENT', code: 'ENT', count: 582, solved: 0 },
    ]);
    assert.deepEqual(rows.map((r) => r.code), ['RAD', 'ENT', 'PHM']);
    assert.deepEqual(neet.pgSubjectsFromStats(undefined), []);
    // The component maps Pharmacology's real code (PHM) to its visual.
    assert.match(read('src/components/neet-pg/NeetPgLanding.tsx'), /SUBJECT_VISUAL\.PHM = SUBJECT_VISUAL\.PHR/);
    assert.doesNotMatch(read('src/components/neet-pg/NeetPgLanding.tsx'), /getSubjects\(\)|live from API|href="\/inicet"|href="\/exams\/(cms|usmle)"|href="\/neet-pg\/vs-upsc-cms"/);
});

test('/neet-pg year tiles: only real years with a paper\'s worth of questions; "1 Q" not "1 Qs"', () => {
    const tiles = neet.yearTilesFromStats([
        { year: 2023, count: 1, solved: 0 },
        { year: 2025, count: 3540, solved: 0 },
        { year: 0, count: 900, solved: 0 },
        { year: 2024, count: 2, solved: 0 },
        { year: 2021, count: 180, solved: 0 },
    ]);
    assert.deepEqual(tiles.map((t) => t.year), [2025, 2021]);
    assert.equal(neet.yearSpanLabel(tiles), '2021–2025');
    assert.equal(neet.yearSpanLabel([{ year: 2025, count: 60, solved: 0 }]), '2025');
    assert.equal(neet.yearSpanLabel([]), '');
    assert.equal(neet.questionCountLabel(1), '1 Q');
    assert.equal(neet.questionCountLabel(3540), '3,540 Qs');
});

test('public nav: on public marketing routes only (never on app pages or pages with their own shell)', () => {
    for (const p of ['/cms', '/cms/vs-neet-pg', '/neet-pg', '/ini-cet', '/usmle', '/blog', '/blog/some-post',
        '/guides/fmge-complete-guide', '/tools/score-calculator', '/about', '/privacy-policy', '/government-doctor-jobs', '/exams/cms']) {
        assert.ok(nav.isPublicNavPath(p), p);
    }
    for (const p of ['/', '/questions', '/questions/neet-pg/practice', '/dashboard', '/resources', '/contact',
        '/login', '/register', '/subscription', '/jobs', '/cmsx', '/blogger', null, '']) {
        assert.equal(nav.isPublicNavPath(p), false, String(p));
    }
    const layout = read('src/app/layout.tsx');
    assert.match(layout, /<PublicNav \/>\s*\n\s*<main id="main-content">/);
    // The homepage shares the same bar, and "Log in" is no longer hidden below sm.
    assert.match(read('src/app/_landing/LandingPage.tsx'), /<PublicNavBar \/>/);
    assert.doesNotMatch(read('src/components/PublicNav.tsx'), /hidden sm:inline-flex/);
});

test('blog: question-bank links use parameters the bank reads; internal links resolve; no self-review', () => {
    const allowedExam = new Set(['cms', 'neet-pg', 'ini-cet', 'fmge', 'usmle']);
    const allowedParams = new Set(['exam', 'subject', 'year', 'q', 'bookmarked']);
    const problems = [];
    for (const post of blog.getAllPosts()) {
        const text = [post.body ?? '', post.primaryCta?.href ?? '', ...(post.relatedExamPaths ?? [])].join('\n');
        for (const m of text.matchAll(/\/questions\?([A-Za-z0-9_=&+%.-]+)/g)) {
            const params = new URLSearchParams(m[1]);
            for (const [k, v] of params) {
                if (!allowedParams.has(k)) problems.push(`${post.slug}: ?${k}=`);
                if (k === 'exam' && !allowedExam.has(v)) problems.push(`${post.slug}: exam=${v}`);
            }
        }
        for (const m of text.matchAll(/\]\((\/blog\/([a-z0-9-]+))\)/g)) {
            if (['tag', 'category', 'author'].includes(m[2])) continue;
            if (!blog.getPostBySlug(m[2])) problems.push(`${post.slug}: broken ${m[1]}`);
        }
        if (/\(\/authors\//.test(text)) problems.push(`${post.slug}: /authors/ link`);
        if (text.includes("'/inicet'") || (post.relatedExamPaths ?? []).includes('/inicet')) problems.push(`${post.slug}: /inicet`);
        // A named author may not "review" their own post (the editorial team
        // authoring and reviewing as a team is fine).
        if (post.authorId && post.authorId !== 'crackcms-editorial' && post.authorId === post.reviewedBy) {
            problems.push(`${post.slug}: self-reviewed`);
        }
        if (/AIIMS-trained/.test(post.body ?? '')) problems.push(`${post.slug}: AIIMS-trained`);
    }
    assert.deepEqual(problems, []);
});

test('blog: UPSC CMS posts use the real marking (one-third of 2.08) and the CBT format', () => {
    for (const post of blog.getAllPosts().filter((p) => /upsc-cms|cms-/.test(p.slug))) {
        const text = `${post.title}\n${post.description}\n${post.body}\n${JSON.stringify(post.faqs ?? [])}`;
        assert.doesNotMatch(text, /\+3\s*\/\s*-1|CSAT|-1 Mark per Wrong/i, post.slug);
    }
    const nm = blog.getPostBySlug('negative-marking-strategy-upsc-cms');
    assert.match(nm.body, /\+2\.08/);
    assert.match(nm.body, /\+0\.23 \| Attempt/);
    assert.match(nm.body, /\| 25% \| 0\.00 \|/, 'a blind guess has zero expected value');
    assert.doesNotMatch(nm.body, /-0\.00/);
    const omr = blog.getPostBySlug('omr-filling-mistakes-upsc-cms');
    assert.match(omr.body, /computer-based test/);
    assert.doesNotMatch(blog.getPostBySlug('time-management-upsc-cms-paper').body, /OMR Bubbling|Paper I \(General Medicine \+ Surgery\)/);

    // No OMR-sheet advice for UPSC CMS unless the same sentence says there is
    // none ("no OMR sheet", "not pen-and-paper"). A stray "do not skip" in the
    // sentence does not count. The OMR-mistakes post is about pen-and-paper
    // exams (its CBT banner is checked above).
    const OMR = /pen-and-paper OMR|OMR (sheet|transfer)|transfer sheet|pencil \+ eraser|erasures? on OMR|\bbubbl/i;
    const SAYS_NONE = /\bno (OMR|answer[- ]sheet|answer-transfer|transfer)|\bnot (a )?pen-and-paper|\bwithout (an )?OMR/i;
    const offenders = [];
    for (const post of blog.getAllPosts().filter((p) => /upsc-cms|cms-/.test(p.slug) && p.slug !== omr.slug)) {
        const text = [post.title, post.description, post.excerpt, post.body ?? '', ...(post.faqs ?? []).flatMap((f) => [f.q, f.a])].join('\n');
        for (const sentence of text.split(/(?<=[.!?])\s+|\n/)) {
            const s = sentence.trim();
            if (!s || s.endsWith('?')) continue;
            if (OMR.test(s) && !SAYS_NONE.test(s)) offenders.push(`${post.slug}: ${s.slice(0, 100)}`);
            // One-third of 2.08 marks, not "-0.33 per wrong".
            if (/[-–−]\s?0\.33 per wrong/i.test(s)) offenders.push(`${post.slug}: ${s.slice(0, 100)}`);
        }
    }
    assert.deepEqual(offenders, []);
    assert.match(blog.getPostBySlug('upsc-cms-last-5-days-strategy').body, /Practise the CBT review flow/);
});

test('blog: social images use the generated per-post card, never a missing /blog/og file', () => {
    const post = blog.getAllPosts()[0];
    assert.equal(blog.postSocialImagePath(post), `/blog/${post.slug}/opengraph-image`);
    assert.equal(existsSync(path.join(FRONTEND, 'public/blog/og')), false, 'the cover files really are missing');
    assert.match(read('src/app/blog/[slug]/page.tsx'), /image: postSocialImagePath\(post\)/);
    assert.match(read('src/app/blog/feed.xml/route.ts'), /postSocialImagePath\(post\)/);
});

test('blog TOC: headings get the ids the "On this page" links use', () => {
    const items = [
        { id: 'marking-scheme', label: 'UPSC CMS Marking Scheme' },
        { id: 'expected-value', label: 'Expected Value Analysis' },
    ];
    assert.deepEqual(
        toc.assignHeadingIds([{ text: 'UPSC CMS Marking Scheme' }, { text: 'Expected **Value** Analysis' }], items),
        ['marking-scheme', 'expected-value'],
    );
    // Same count, different wording -> paired in order; existing ids are kept.
    assert.deepEqual(toc.assignHeadingIds([{ text: 'Scheme' }, { text: 'EV', id: 'ev' }], items), ['marking-scheme', null]);
    // An id already on the page is not reused.
    assert.deepEqual(toc.assignHeadingIds([{ text: 'UPSC CMS Marking Scheme' }], items.slice(0, 1), (id) => id === 'marking-scheme'), [null]);
    const layout = read('src/components/BlogPostLayout.tsx');
    assert.match(layout, /<details className="lg:hidden/);
    assert.match(layout, /hidden lg:block rounded-2xl/);
});

test('blog comments stay hidden while Giscus is unconfigured (flag read from a plain module)', async () => {
    const giscus = await import('../../src/components/giscusConfig.ts');
    assert.equal(giscus.GISCUS_CONFIGURED, Boolean(giscus.GISCUS_REPO_ID && giscus.GISCUS_CATEGORY_ID));
    const layout = read('src/components/BlogPostLayout.tsx');
    assert.match(layout, /GISCUS_CONFIGURED && \(/);
    // BlogPostLayout is a Server Component: a value imported from the
    // 'use client' CommentsGiscus file would be a truthy client reference.
    assert.match(layout, /import \{ GISCUS_CONFIGURED \} from '@\/components\/giscusConfig'/);
    assert.doesNotMatch(layout, /^['"]use client['"]/);
    assert.doesNotMatch(read('src/components/CommentsGiscus.tsx'), /Comments are opening soon|export const GISCUS_CONFIGURED/);
});

test('college predictor: the four UPSC CMS services, category thresholds from the vacancy model', () => {
    assert.deepEqual(predictor.CMS_SERVICES.map((s) => s.id), ['chs', 'railways', 'ndmc', 'mcd']);
    assert.equal(predictor.CMS_SERVICES[0].group, 'Category I');
    assert.ok(predictor.CMS_SERVICES.slice(1).every((s) => s.group === 'Category II'));
    const general = predictor.predictServices(100, 'general');
    assert.equal(general.band, 'safe');
    assert.equal(general.illustrativeLimit, Math.round(ep.UPSC_CMS_CYCLE.vacancies * 0.405));
    assert.equal(predictor.predictServices(general.illustrativeLimit, 'general').band, 'moderate');
    assert.equal(predictor.predictServices(general.illustrativeLimit + 1, 'general').band, 'reach');
    assert.equal(predictor.predictServices(10, 'ews').categoryLabel, 'EWS');
    assert.equal(predictor.predictServices(0, 'general'), null);
    assert.equal(predictor.predictServices(Number.NaN, 'sc'), null);
    const ui = read('src/app/tools/college-predictor/page.tsx') + read('src/app/tools/college-predictor/CollegePredictor.tsx');
    assert.doesNotMatch(ui, /AIIMS New Delhi, JIPMER|urClosingRank|UR cutoff ~|Hospital & Department/);
    assert.match(ui, /not official UPSC closing ranks/);
});

test('/resources and /cms state the real UPSC CMS attempts rule', () => {
    assert.match(ep.UPSC_CMS_PATTERN.attemptsRule, /No fixed limit/);
    assert.doesNotMatch(ep.UPSC_CMS_PATTERN.attemptsFaq, /6 attempts|9 attempts/);
    const resources = read('src/app/resources/page.tsx');
    assert.match(resources, /UPSC_CMS_PATTERN\.attemptsRule/);
    assert.doesNotMatch(resources, /guide\.eligibility\.attempts/);
    assert.match(resources, /flex flex-wrap gap-2 mb-6/);
    assert.match(read('src/app/cms/page.tsx'), /UPSC_CMS_PATTERN\.attemptsRule/);
});

test('PostHog: a consent re-grant clears the opt-out PostHog persisted earlier', () => {
    const code = posthogLoaderScript('phc_test', { api_host: 'https://us.i.posthog.com' });
    assert.doesNotThrow(() => new vm.Script(code));
    const sandbox = { document: { createElement: () => ({}), getElementsByTagName: () => [{ parentNode: { insertBefore() {} } }] } };
    sandbox.window = sandbox;
    vm.runInNewContext(code, sandbox);
    const opts = sandbox.window.posthog._i[0][1];
    assert.equal(opts.api_host, 'https://us.i.posthog.com', 'JSON options are kept');
    assert.equal(typeof opts.loaded, 'function');
    let optedIn = 0;
    opts.loaded({ has_opted_out_capturing: () => true, opt_in_capturing: () => { optedIn += 1; } });
    assert.equal(optedIn, 1);
    opts.loaded({ has_opted_out_capturing: () => false, opt_in_capturing: () => { optedIn += 1; } });
    assert.equal(optedIn, 1, 'no extra $opt_in event when nothing was opted out');
});

test('analytics relay feeds every internal-dashboard funnel stage', () => {
    for (const e of ['page_view', 'blog_view', 'question_solve', 'ai_tutor_message', 'register_intent']) {
        assert.ok(RELAYED_EVENTS.has(e), e);
    }
});

test('privacy: consent copy matches the cookieless counter; no pre-consent connections to Google', () => {
    assert.match(read('src/components/ConsentBanner.tsx'), /without cookies or personal data \(Simple Analytics\)/);
    const layout = read('src/app/layout.tsx');
    assert.doesNotMatch(layout, /rel="preconnect" href="https:\/\/(www\.googletagmanager|www\.google-analytics|fonts\.googleapis|fonts\.gstatic)/);
    assert.equal(existsSync(path.join(FRONTEND, 'public/ads.txt')), false, 'no placeholder AdSense publisher id');
    assert.equal(existsSync(path.join(FRONTEND, 'sentry.client.config.ts')), false, 'dead Sentry config removed');
});

test('contract pages describe the plans actually sold (only the yearly plan is unlimited)', () => {
    const terms = read('src/app/terms/page.tsx');
    assert.doesNotMatch(terms, /unlock unlimited AI tutor sessions/);
    assert.match(terms, /PREMIUM_PLANS/);
    assert.doesNotMatch(read('src/app/privacy-policy/page.tsx'), /want unlimited AI tutoring|single-\r?\n/);
    assert.equal(meta.stripBrandSuffix('Privacy Policy — CrackCMS by CrackLabs AI'), 'Privacy Policy');
    assert.equal(meta.stripBrandSuffix('Terms & Conditions — CrackCMS by CrackLabs AI'), 'Terms & Conditions');
});

test('reviewers: no unverifiable "AIR-1" medical reviewer on strategy, book or subject pages', () => {
    // String values only (the explanatory comments mention what was removed).
    for (const f of ['src/lib/strategyData.ts', 'src/lib/bookDeepDiveData.ts', 'src/lib/subjectHubData.ts']) {
        assert.doesNotMatch(read(f), /name: 'Dr\. Ananya Reddy'|credentials: '[^']*AIR-1|strategySubtitle: 'Built by/, f);
    }
    for (const f of ['src/app/cms/strategy/page.tsx', 'src/app/cms/books/page.tsx']) {
        assert.doesNotMatch(read(f), /AIR-1 topper|built by (an )?UPSC CMS AIR-1/i, f);
    }
    assert.doesNotMatch(read('src/content/authors.ts'), /'AIIMS-trained|cracklabs\.app\/authors\/|credential: 'MBBS, MD, FRCP/);
    assert.doesNotMatch(read('src/lib/cutoffData.ts'), /has not yet been held|is scheduled for 02 August 2026/);
    // keyTrends: no per-year counts that contradict the fixed split, no unsourced "firsts".
    assert.doesNotMatch(read('src/lib/pyqYearData.ts'), /PSM continued to gain weight|PSM had 40 questions|Multiple-best-answer \(MBA\)|top 50 rankers|0\.33 negative marking|\d+ direct (STEMI|trauma|questions)/);
    // Uncited per-year specifics (wave 3): no source, and no image-based CMS rows back the first.
    assert.doesNotMatch(read('src/lib/pyqYearData.ts'), /'Image-based radiology questions|'Included questions on (national COVID-19|geriatric)/);
});

function pngSize(file) {
    const buf = readFileSync(file);
    assert.equal(buf.toString('ascii', 1, 4), 'PNG', `${file} is a PNG`);
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

test('icons and OG image are real files with the sizes they are declared at', () => {
    const manifest = JSON.parse(read('public/manifest.json'));
    for (const icon of manifest.icons) {
        const [w, h] = icon.sizes.split('x').map(Number);
        assert.deepEqual(pngSize(path.join(FRONTEND, 'public', icon.src)), { width: w, height: h }, icon.src);
    }
    assert.ok(manifest.icons.some((i) => i.purpose === 'maskable'));
    assert.deepEqual(pngSize(path.join(FRONTEND, 'public/brand/favicon-32.png')), { width: 32, height: 32 });
    assert.deepEqual(pngSize(path.join(FRONTEND, 'public/brand/apple-touch-icon.png')), { width: 180, height: 180 });
    assert.equal(seo.defaultOgImage, '/brand/og-image.png');
    assert.deepEqual(pngSize(path.join(FRONTEND, 'public', seo.defaultOgImage)), { ...seo.defaultOgImageSize });
    const layout = read('src/app/layout.tsx');
    assert.match(layout, /\/brand\/favicon-32\.png/);
    assert.match(layout, /\/brand\/apple-touch-icon\.png/);
    assert.doesNotMatch(layout, /icon: \[\{ url: "\/cms-circle-logo\.png"/);
});

test('exam landing layout: stats shown once per breakpoint, crumb in the hero container, neutral feature copy', () => {
    const src = read('src/components/ExamLandingLayout.tsx');
    assert.match(src, /hidden lg:grid grid-cols-2/);
    assert.match(src, /bg-card\/50 lg:hidden/);
    assert.match(src, /whitespace-nowrap text-yellow-300/);
    assert.match(src, /mx-auto max-w-7xl px-4 py-3 sm:px-6/);
    assert.doesNotMatch(src, /Adaptive tests|with negative marking and real-time ranking|Every answer links to/);
    for (const page of ['cms', 'ini-cet', 'fmge', 'usmle', 'medical-officer', 'government-doctor-jobs']) {
        assert.doesNotMatch(read(`src/app/${page}/page.tsx`), /<Breadcrumbs/, `${page}: crumb comes from the layout`);
    }
    assert.match(read('src/app/government-doctor-jobs/page.tsx'), /secondaryCta: \{ label: 'Browse vacancies', href: '\/jobs' \}/);
});

test('footer: same logo as the rest of the site; no login-only links for signed-out visitors', () => {
    const footer = read('src/components/Footer.tsx');
    assert.match(footer, /src="\/cms-circle-logo\.png"/);
    for (const href of ['/jobs', '/tokens', '/leaderboard', '/bookmarks', '/analytics']) {
        assert.ok(!footer.includes(`href: '${href}'`), href);
    }
});
