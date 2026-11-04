// Regression tests for the wave-3 public-site fixes: bylines only for
// profiles we can stand behind (no unconfirmed credentialed author), trust
// pages that describe only the review process that exists, guide
// copy without unbacked features, JSX text that keeps its spaces, cutoff copy
// that promises only what the page shows, blog card styles, the public llms
// files, the /exams NEET PG year tiles, in-page anchors below the sticky
// nav, analytics staying a free feature in marketing copy, and blog CTAs
// into the (premium) simulator next to the real UPSC CMS paper pattern.
// Run (from frontend/): node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/public-wave3.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel) => readFileSync(path.join(FRONTEND, rel), 'utf8');

const blog = await import('../../src/lib/blog.ts');
const { authors, getAuthor, RETIRED_AUTHOR_SLUGS } = await import('../../src/content/authors.ts');
const { cutoffSummary, cutoffMetaDescription } = await import('../../src/lib/cutoffCopy.ts');
const { CMS_CUTOFFS } = await import('../../src/lib/cutoffData.ts');
const bank = await import('../../src/lib/bankStats.ts');
const { UPSC_CMS_PATTERN } = await import('../../src/lib/examPatterns.ts');

function walk(dir) {
    if (!existsSync(dir)) return [];
    return readdirSync(dir).flatMap((name) => {
        const p = path.join(dir, name);
        return statSync(p).isDirectory() ? walk(p) : [p];
    });
}

test('bylines: every post credits a registered profile; no unverified credentialed author', () => {
    const problems = [];
    for (const post of blog.getAllPosts()) {
        for (const slug of [post.authorId, post.reviewedBy].filter(Boolean)) {
            if (!authors[slug]) problems.push(`${post.slug}: unknown profile ${slug}`);
        }
        if (post.author !== getAuthor(post.authorId).name) problems.push(`${post.slug}: byline "${post.author}"`);
        if (/Aarav|MBBS, MD \(Internal Medicine\)|Senior Editor/.test([post.author, post.authorRole, post.body].join('\n'))) {
            problems.push(`${post.slug}: retired byline`);
        }
    }
    assert.deepEqual(problems, []);
    // Only profiles the owner can stand behind; none claims a medical degree.
    assert.deepEqual(Object.keys(authors), ['crackcms-editorial']);
    for (const a of Object.values(authors)) {
        assert.doesNotMatch(`${a.name} ${a.credential} ${a.bio}`, /MBBS|\bMD\b|\bMS\b|FRCP|AIIMS|internist/i, a.slug);
    }
    // The retired archive URL redirects to the profile now credited.
    for (const [retired, successor] of Object.entries(RETIRED_AUTHOR_SLUGS)) {
        assert.equal(authors[retired], undefined, retired);
        assert.ok(authors[successor], successor);
    }
    assert.equal(RETIRED_AUTHOR_SLUGS['dr-aarav-mehta'], 'crackcms-editorial');
    const page = read('src/app/blog/author/[slug]/page.tsx');
    assert.match(page, /const successor = RETIRED_AUTHOR_SLUGS\[slug\];\s+if \(successor\) permanentRedirect\(`\/blog\/author\/\$\{successor\}`\);/);
    assert.equal(existsSync(path.join(FRONTEND, 'src/components/ReviewerByline.tsx')), false, 'unused fabricated-reviewer byline removed');
    assert.doesNotMatch(read('src/components/StrategyLayout.tsx'), /AIR-1/);
    assert.doesNotMatch(read('src/app/editorial-policy/page.tsx'), /\(editorial lead name\)|Dr\. \(/);
});

// The trust pages describe the review process the product implements: AI
// drafts, the automatic answer-key mismatch flag, the editorial team's
// cross-check and "Verified by Admin" badge, revision snapshots and learner
// reports. No unconfirmed clinician or specialist reviewers, sign-offs,
// boards, audit quotas or red team, and no badge, field or e-mail that was
// never built ('Recently corrected', last_reviewed, mails to all attempters).
const TRUST_PAGES = ['src/app/about/page.tsx', 'src/app/editorial-policy/page.tsx',
    'src/app/medical-review-policy/page.tsx', 'src/app/ai-attribution-policy/page.tsx', 'src/components/LegalLayout.tsx'];

test('trust pages: only the review process that exists (no unconfirmed clinicians, boards or unbuilt features)', () => {
    for (const f of TRUST_PAGES) {
        const src = read(f);
        assert.doesNotMatch(src, /clinicians?\b|MD\/MS|medical board|chief medical officer|red-team|Recently corrected/i, f);
        assert.doesNotMatch(
            src,
            /MBBS plus|post-PG|Editorial Board|team of medical graduates|last_reviewed|\d+\+ AI tutor responses|re-audit|Clinically[- ]reviewed|medical doctors|medical-review team|who attempted the question|clinical-grade|Every claim cites/i,
            f,
        );
    }
    const review = read('src/app/medical-review-policy/page.tsx');
    assert.match(review, /Content is checked by the CrackCMS Editorial Team/);
    assert.match(review, /<strong>Automatic answer check<\/strong> — when the AI&apos;s answer disagrees with the stored answer key/);
    assert.match(review, /created live and are not\s+reviewed before you see them/);
    assert.match(review, /lastUpdated="November 1, 2026"/);
    // The badge the policies cite is the one the question bank renders.
    assert.match(review, /&quot;Verified by Admin&quot; badge/);
    assert.match(read('src/components/question/ExamQuestionBank.tsx'), /Verified by Admin/);
    const editorial = read('src/app/editorial-policy/page.tsx');
    assert.match(editorial, /NEET PG and INI-CET questions are mostly memory-based recalls/);
    assert.doesNotMatch(editorial, /questions_fixture\.json|transcribed from official conducting-body publications/);
    const policy = read('src/app/ai-attribution-policy/page.tsx');
    assert.match(policy, /<li>Editorially reviewed medical articles, guides, and study strategies<\/li>/);
    assert.match(policy, /<strong>Editorial review<\/strong> — checked against standard textbooks by the CrackCMS Editorial Team/);
    assert.doesNotMatch(policy, /All medical content on CrackCMS undergoes/);
    assert.match(read('src/components/LegalLayout.tsx'), /a free study desk for MBBS graduates sitting UPSC CMS, NEET PG and similar exams\./);
    assert.match(read('src/app/about/page.tsx'), /the editorial team checks them against standard textbooks/);
});

test('no public page, post or byline claims a medical review nobody performs', () => {
    const appDirs = ['about', 'ai-attribution-policy', 'blog', 'cms', 'contact', 'cookie-policy', 'disclaimer',
        'editorial-policy', 'exams', 'fmge', 'government-doctor-jobs', 'guides', 'ini-cet', 'medical-officer',
        'medical-review-policy', 'neet-pg', 'privacy-policy', 'refund-policy', 'resources', 'terms', 'tools', 'usmle', '_landing'];
    const components = ['BlogPostLayout.tsx', 'BlogCard.tsx', 'BookDeepDiveLayout.tsx', 'CutoffLayout.tsx', 'StrategyLayout.tsx',
        'SubjectHubLayout.tsx', 'LegalLayout.tsx', 'GuideLayout.tsx', 'ExamLandingLayout.tsx', 'ComparisonLayout.tsx', 'Footer.tsx',
        'PublicNav.tsx', 'neet-pg/NeetPgLanding.tsx', 'exams/ExamMicrosite.tsx', 'ui/MagicBento.tsx'];
    const files = [
        ...appDirs.flatMap((d) => walk(path.join(FRONTEND, 'src/app', d))),
        ...components.map((f) => path.join(FRONTEND, 'src/components', f)),
        ...walk(path.join(FRONTEND, 'src/content')),
        ...walk(path.join(FRONTEND, 'src/lib')),
        ...['public/llms.txt', 'public/llms-full.txt'].map((f) => path.join(FRONTEND, f)),
    ].filter((f) => /\.(tsx?|txt)$/.test(f) && existsSync(f));
    assert.ok(files.length > 250, `scanned ${files.length} files`);
    const offenders = [];
    for (const f of files) {
        const m = readFileSync(f, 'utf8').match(
            /medically[- ]reviewed|clinician[- ]review|clinically[- ]review|by our medical team|medical consensus answer|built by clinicians/i,
        );
        if (m) offenders.push(`${path.relative(FRONTEND, f)}: "${m[0]}"`);
    }
    assert.deepEqual(offenders, []);
    // Bylines name the editorial review for what it is.
    assert.match(read('src/components/BlogPostLayout.tsx'), /Reviewed by\{' '\}\s+<strong className="text-foreground">\{reviewer\.name\}<\/strong>/);
    assert.match(read('src/app/blog/author/[slug]/page.tsx'), /Reviewed by \{author\.name\} \(\{reviewed\.length\}\)/);
    assert.match(read('src/components/SubjectHubLayout.tsx'), /Reviewed by <span className="font-semibold text-foreground">\{c\.reviewer\.name\}<\/span>/);
});

test('blog: every content file is a registered post (no orphan stale drafts)', () => {
    const files = readdirSync(path.join(FRONTEND, 'src/content/blog'))
        .filter((f) => f.endsWith('.ts'))
        .map((f) => f.slice(0, -3))
        .sort();
    assert.deepEqual(files, blog.getAllPosts().map((p) => p.slug).sort());
    assert.ok(!files.includes('upsc-cms-2026-application-form'), 'stale 2026 application-form draft removed');
});

test('guides: editorial-team byline, no clinician persona, no unbacked features', () => {
    const files = walk(path.join(FRONTEND, 'src/app/guides')).filter((f) => f.endsWith('.tsx'));
    assert.ok(files.length >= 9, `scanned ${files.length} guide files`);
    for (const f of files) {
        assert.doesNotMatch(
            readFileSync(f, 'utf8'),
            /Dr\. CrackCMS|practi[cs]ing clinicians?\b|clinician-reviewed|AIR prediction/i,
            path.relative(FRONTEND, f),
        );
    }
    const ai = read('src/app/guides/ai-in-medical-education/page.tsx');
    assert.doesNotMatch(ai, /11\+|DeepSeek|Together|AI\/ML API|NVIDIA|automatically increases difficulty|for every claim/);
    assert.match(ai, /<strong>Weak topics<\/strong> practice mode/);
    assert.doesNotMatch(read('src/app/guides/upsc-cms-complete-guide/page.tsx'), /Specialists|and Defence\./);
    assert.doesNotMatch(read('src/app/cms/salary/page.tsx'), /Specialists/);
    assert.doesNotMatch(read('src/app/exams/_data.ts'), /Ordnance Factories/);
});

// A JSX line break next to inline markup drops the space: "...</strong>" then
// a text line renders "Examinationis", and a text line then "<a>" renders
// "emailcrack...". Use {' '} at the line end.
const INLINE_CLOSE_AT_END = /<\/(strong|em|a|Link|code|b|i)>$/;
const INLINE_OPEN_AT_START = /^<(strong|em|a|Link|code|b|i)\b[^>]*>(?!\s)/;

test('public pages: no JSX line break that swallows the space next to inline markup', () => {
    const roots = ['about', 'ai-attribution-policy', 'blog', 'cms', 'cookie-policy', 'disclaimer', 'editorial-policy',
        'exams', 'fmge', 'government-doctor-jobs', 'guides', 'ini-cet', 'medical-officer', 'medical-review-policy',
        'neet-pg', 'privacy-policy', 'refund-policy', 'terms', 'tools', 'usmle', '_landing'];
    const files = roots.flatMap((d) => walk(path.join(FRONTEND, 'src/app', d))).filter((f) => f.endsWith('.tsx'));
    assert.ok(files.length > 60, `scanned ${files.length} files`);
    const offenders = [];
    for (const f of files) {
        const lines = readFileSync(f, 'utf8').split(/\r?\n/);
        for (let i = 0; i < lines.length - 1; i++) {
            const a = lines[i].trim();
            const b = lines[i + 1].trim();
            if (!a || !b || /^(\/\/|\*|\/\*|import |export |const |return\b)/.test(a)) continue;
            const where = `${path.relative(FRONTEND, f)}:${i + 1}`;
            if (INLINE_CLOSE_AT_END.test(a) && /^[A-Za-z0-9(&]/.test(b)) offenders.push(`${where} ${a.slice(-40)} | ${b.slice(0, 30)}`);
            if (/[A-Za-z0-9,;:.)]$/.test(a) && !a.startsWith('{') && INLINE_OPEN_AT_START.test(b)) {
                offenders.push(`${where} ${a.slice(-40)} | ${b.slice(0, 30)}`);
            }
        }
    }
    assert.deepEqual(offenders, []);
    // The four spots the review found.
    assert.match(read('src/app/guides/upsc-cms-complete-guide/page.tsx'), /Examination<\/strong>\{' '\}/);
    assert.match(read('src/app/medical-review-policy/page.tsx'), /or email\{' '\}/);
    assert.match(read('src/app/ai-attribution-policy/page.tsx'), /hosted at\{' '\}/);
    assert.match(read('src/app/guides/neet-pg-complete-guide/page.tsx'), /superspecialty\)\.\{' '\}/);
});

test('cutoff pages promise only what they show (no topper scores or trends without data)', () => {
    for (const c of Object.values(CMS_CUTOFFS)) {
        const text = `${cutoffSummary(c)} ${cutoffMetaDescription(c)}`;
        if (c.toppers.length === 0) assert.doesNotMatch(text, /topper/i, String(c.year));
        if (c.trend.length === 0) assert.doesNotMatch(text, /year-over-year/i, String(c.year));
        if (c.cutoffs.length === 0) {
            assert.match(cutoffSummary(c), /comes with the final result/, String(c.year));
            assert.doesNotMatch(cutoffMetaDescription(c), /qualifying marks for|See if you would have qualified/, String(c.year));
        } else {
            assert.match(cutoffMetaDescription(c), /See if you would have qualified\.$/, String(c.year));
        }
    }
    assert.equal(CMS_CUTOFFS[2026].cutoffs.length, 0, '2026 has no published cutoff yet');
    const full = {
        examName: 'UPSC CMS', year: 2030,
        cutoffs: [{ category: 'General', cutoff: 300 }],
        toppers: [{ rank: 1, name: 'A', score: '400' }],
        trend: [{ category: 'General', prevYear: 290, thisYear: 300 }],
    };
    assert.equal(
        cutoffSummary(full),
        'Category-wise qualifying marks for UPSC CMS 2030, topper scores and year-over-year trends, and answers to common questions about this cycle.',
    );
    const layout = read('src/components/CutoffLayout.tsx');
    assert.doesNotMatch(layout, /cutoff marks, topper scores|topper scores, and/);
    assert.match(layout, /\{c\.cutoffs\.length === 0 \? \(/, 'an empty cycle shows a notice instead of an empty grid');
});

test('blog cards and tag chips use theme utilities (blog-card / blog-tag-chip were never defined)', () => {
    const css = read('src/app/globals.css');
    for (const f of ['src/components/BlogCard.tsx', 'src/components/BlogPostLayout.tsx', 'src/app/blog/author/[slug]/page.tsx']) {
        const src = read(f);
        for (const cls of ['blog-card', 'blog-card-featured', 'blog-card-featured-cover', 'blog-card-featured-body', 'blog-tag-chip']) {
            if (new RegExp(`className="[^"]*\\b${cls}(?![\\w-])`).test(src)) {
                assert.ok(css.includes(`.${cls}`), `${f} uses .${cls}, which globals.css does not define`);
            }
        }
    }
    const card = read('src/components/BlogCard.tsx');
    // Full-height flex columns: cards in a grid row line up (the /blog featured row and explorer).
    assert.match(card, /className="group flex h-full flex-col rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary\/40"/);
    assert.match(card, /className="group flex h-full flex-col overflow-hidden rounded-3xl border border-border bg-card transition-colors hover:border-primary\/40"/);
    assert.match(card, /<Badge className="mr-2 bg-primary/);
});

test('public llms files and the AI policy: no provider count, no DeepSeek/Ollama, no internal API or env names', () => {
    const files = { 'public/llms-full.txt': read('public/llms-full.txt'), 'public/llms.txt': read('public/llms.txt') };
    for (const [name, text] of Object.entries(files)) {
        assert.doesNotMatch(text, /\b11[- ]provider|\b11 providers|\b11\+|DeepSeek|Ollama|Together|AI\/ML API/i, name);
        assert.doesNotMatch(text, /\/admin\/|_API_KEY|SECRET|RAZORPAY_KEY|SUPABASE_URL|ondigitalocean\.app|DATABASE_URL/, name);
        assert.doesNotMatch(text, /advanced analytics|Deep Analytics|single-device|0\.33 per wrong|scheduled for 02 August 2026|review board|MBBS, MD/i, name);
        assert.ok(text.includes(bank.CMS_PYQ_COUNT), `${name} states ${bank.CMS_PYQ_COUNT}`);
    }
    const short = files['public/llms.txt'];
    assert.match(short, /https:\/\/cracklabs\.app\/ini-cet \|/);
    assert.doesNotMatch(short, /cracklabs\.app\/inicet\b|BaiduspideryandexBot|trained on standard medical textbooks/);
    const policy = read('src/app/ai-attribution-policy/page.tsx');
    assert.match(policy, /\{CMS_PYQ_COUNT\} UPSC CMS previous-year questions/);
    assert.doesNotMatch(policy, /1,920\+|11 providers|FMGE, and USMLE question banks|X-AI-Trainable/);
    const privacy = read('src/app/privacy-policy/page.tsx');
    assert.doesNotMatch(privacy, /DeepSeek|Together|AI\/ML API/);
    assert.match(privacy, /OmniRoute AI gateway, Groq, Cerebras, Google Gemini, Cohere, OpenRouter, GitHub Models,/);
});

test('NEET PG microsites: year tiles only for real recall years; anchors clear the sticky nav; one footer', () => {
    const data = read('src/app/exams/_data.ts');
    assert.match(data, /pyqYears: \[2025, 2021, 2020, 2018\],\s+pyqYearsNote: "Click a year to practise that year's NEET PG recall questions\."/);
    const micro = read('src/components/exams/ExamMicrosite.tsx');
    assert.match(micro, /\{cfg\.pyqYearsNote \?\? 'Click a year to attempt the full paper in Practice or Exam mode\.'\}/);
    assert.match(micro, /<section id="subjects" className="scroll-mt-20 /);
    assert.match(micro, /<section id="high-yield" className=\{`scroll-mt-20 /);
    const landing = read('src/components/neet-pg/NeetPgLanding.tsx');
    for (const id of ['years', 'subjects', 'high-yield']) {
        assert.match(landing, new RegExp(`<section id="${id}" className="scroll-mt-20 `), id);
    }
    assert.doesNotMatch(landing, /<footer|NEET PG microsite|Start \$\{featuredYear\} Paper/);
    assert.match(landing, /`Start \$\{featuredYear\} recalls`/);
});

test('analytics is free: marketing and contract copy never sells it as a premium feature', () => {
    for (const f of ['src/app/_landing/LandingPage.tsx', 'src/app/terms/page.tsx', 'src/lib/seo.ts',
        'src/components/ui/MagicBento.tsx', 'src/lib/paywall/paywallStore.ts', 'public/llms-full.txt', 'public/llms.txt']) {
        const text = read(f);
        assert.doesNotMatch(text, /Deep Analytics|advanced analytics|Unlock[^.\n]*analytics|"Analytics & Weak Areas"|rank predictions/i, f);
    }
    assert.doesNotMatch(read('src/lib/seo.ts'), /premium plans[^"\n]*analytics/i);
    assert.match(read('src/app/terms/page.tsx'), /access to the question[\s\S]{0,40}bank, mock tests, and analytics/);
});

// Full paper mocks and PYQ-year simulations are premium (a free account's
// /tests/{id}/start/ answers 402 upgrade_required), so a CTA into /simulator
// must not say "free". The Paper I vs Paper II post used to state 200
// questions per paper with Surgery in Paper I.
test('blog: simulator CTAs promise no free mocks; the Paper I vs II post states the real UPSC CMS pattern', () => {
    const simulatorPosts = blog.getAllPosts().filter((p) => p.primaryCta?.href?.startsWith('/simulator'));
    assert.ok(simulatorPosts.length >= 2, `found ${simulatorPosts.length} posts linking to /simulator`);
    for (const p of simulatorPosts) assert.doesNotMatch(p.primaryCta.label, /\bfree\b/i, p.slug);
    assert.equal(blog.getPostBySlug('time-management-upsc-cms-paper').primaryCta.label, 'Try a Timed Mock Test');

    const post = blog.getPostBySlug('upsc-cms-paper-1-vs-paper-2-strategy');
    const faqs = JSON.stringify(post.faqs);
    assert.doesNotMatch(`${post.body}\n${faqs}`, /\b200 ?(questions|Q)\b|General Surgery|Medicine \+ Surgery|Paper II covers: OBG, Paediatrics/i);
    const sections = post.body.split(/^## /m);
    for (const paper of UPSC_CMS_PATTERN.papers) {
        const section = sections.find((s) => s.startsWith(`${paper.name}: Composition`)) ?? '';
        assert.ok(section.includes(`- Total: ${paper.questions} questions, ${paper.marks} marks, ${paper.durationMinutes} minutes`), paper.name);
        for (const s of paper.subjects) {
            assert.ok(section.includes(`- ${s.name}: ${s.questions} questions`), `${paper.name}: ${s.name}`);
        }
    }
    assert.match(faqs, /Each paper has 120 questions, carries 250 marks and lasts two hours\./);
    assert.match(faqs, /Paper I covers General Medicine \(96 questions[^)]*\) and Paediatrics \(24\)/);
});

test('housekeeping: tsconfig no longer excludes the deleted Sentry client config', () => {
    assert.doesNotMatch(read('tsconfig.json'), /sentry\.client\.config/);
    assert.equal(existsSync(path.join(FRONTEND, 'sentry.client.config.ts')), false);
});
