// Regression tests for robots / sitemap / canonicals / structured data /
// internal links on the public site (PUB-01..04, PUB-09, PUB-16, PUB-17,
// PUB-21, PUB-23, PUB-30, PUB-31, PUB-38, PUB-41, PUB-06, PUB-07, PUB-18).
// Run (from frontend/; quoted globs — the bare directory form fails with
// ERR_UNSUPPORTED_DIR_IMPORT on Node 22):
//   node --import ./tests/unit/register-ts-alias.mjs --test "tests/unit/*.test.mjs" "tests/unit/*.test.ts"
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const SRC = path.join(FRONTEND, 'src');
const read = (rel) => readFileSync(path.join(FRONTEND, rel), 'utf8');

// Next's own serialisers, so the assertions are about the text Next serves.
const { resolveRobots, resolveSitemap } = require(path.join(FRONTEND, 'node_modules/next/dist/build/webpack/loaders/metadata/resolve-route-data.js'));

const robots = (await import('../../src/app/robots.ts')).default;
const sitemap = (await import('../../src/app/sitemap.ts')).default;
const blog = await import('../../src/lib/blog.ts');
const { CMS_VS_NEETPG, NEETPG_VS_USMLE, FMGE_VS_NEXT } = await import('../../src/lib/comparisonData.ts');
const { getCmsYear, getAllCmsYears } = await import('../../src/lib/pyqYearData.ts');
const { stripBrandSuffix, jsonLdString, softwareAppSchema, websiteSchema } = await import('../../src/lib/metadata.ts');
const { questionBankHref } = await import('../../src/lib/seo.ts');

test('static public/robots.txt and public/sitemap.xml no longer shadow the generated routes', () => {
    assert.equal(existsSync(path.join(FRONTEND, 'public/robots.txt')), false);
    assert.equal(existsSync(path.join(FRONTEND, 'public/sitemap.xml')), false);
});

test('robots.txt: real prefixes, no /_next block, one group per user agent', () => {
    const text = resolveRobots(robots());
    const lines = text.split('\n');
    const disallows = lines.filter((l) => l.startsWith('Disallow:')).map((l) => l.slice(9).trim());
    for (const p of ['/admin', '/dashboard', '/api', '/tokens', '/questions', '/practice', '/jobs', '/settings']) {
        assert.ok(disallows.includes(p), `Disallow: ${p}`);
    }
    assert.ok(!disallows.some((p) => p.startsWith('/_next')), '/_next/ assets stay crawlable');
    assert.ok(!disallows.includes('/dashboard/'), 'no trailing-slash prefixes that miss /dashboard');
    const agents = lines.filter((l) => /^User-Agent:/i.test(l)).map((l) => l.split(':')[1].trim());
    assert.equal(new Set(agents).size, agents.length, 'each user agent appears once');
    assert.ok(agents.includes('*') && agents.includes('Googlebot') && agents.includes('GPTBot'));
    assert.match(text, /Sitemap: https:\/\/www\.cracklabs\.app\/sitemap\.xml/);
});

test('sitemap: unique URLs, no login-only or redirecting routes, no thin tag pages', () => {
    const entries = sitemap();
    const urls = entries.map((e) => e.url);
    assert.equal(new Set(urls).size, urls.length, 'no duplicate URLs');
    const paths = urls.map((u) => new URL(u).pathname);
    for (const bad of ['/jobs', '/practice', '/subscription', '/exams', '/inicet', '/neet-pg/vs-upsc-cms', '/cms/cutoff', '/ai-tutor', '/questions']) {
        assert.ok(!paths.includes(bad), `${bad} is not submitted`);
    }
    for (const good of ['/', '/cms', '/ini-cet', '/tools/score-calculator', '/cms/vs-neet-pg', '/blog']) {
        assert.ok(paths.includes(good), `${good} is submitted`);
    }
    const tagPaths = paths.filter((p) => p.startsWith('/blog/tag/'));
    for (const p of tagPaths) {
        const tag = blog.getTagBySlug(p.split('/').pop());
        assert.ok(tag && tag.count >= blog.MIN_INDEXABLE_TAG_POSTS, `${p} has enough posts`);
    }
    assert.match(resolveSitemap(entries), /^<\?xml/);
});

test('blog tag pages resolve tags with hyphens/symbols, and tag slugs are unique', () => {
    for (const slug of ['ini-cet', 'high-yield', 'acid-base', 'x-ray']) {
        const tag = blog.getTagBySlug(slug);
        assert.ok(tag, `tag ${slug} exists`);
        assert.equal(blog.getPostsByTag(slug).length, tag.count, `${slug} shows its ${tag.count} posts`);
    }
    for (const t of blog.getAllTags()) {
        assert.equal(blog.getPostsByTag(t.slug).length, t.count, `count matches for ${t.slug}`);
    }
    const slugs = blog.getAllTags().map((t) => t.slug);
    assert.equal(new Set(slugs).size, slugs.length);
});

test('every internal /blog/<slug> link in comparisons and exam landings resolves to a post', () => {
    const links = [CMS_VS_NEETPG, NEETPG_VS_USMLE, FMGE_VS_NEXT].flatMap((c) => c.relatedLinks ?? []).map((l) => l.href);
    for (const href of links.filter((h) => h.startsWith('/blog/'))) {
        assert.ok(blog.getPostBySlug(href.slice('/blog/'.length)), `${href} exists`);
    }
    for (const page of ['src/app/cms/page.tsx', 'src/app/ini-cet/page.tsx', 'src/app/usmle/page.tsx']) {
        const src = read(page);
        const block = src.slice(src.indexOf('relatedBlogPosts'));
        const slugs = [...block.matchAll(/slug: '([^']+)'/g)].map((m) => m[1]);
        assert.ok(slugs.length > 0, `${page} lists related posts`);
        for (const s of slugs) assert.ok(blog.getPostBySlug(s), `${page}: /blog/${s} exists`);
    }
});

test('comparison pages carry their real path (FMGE vs NEXT no longer points at /fmge/vs-neet-pg)', () => {
    assert.equal(FMGE_VS_NEXT.path, '/fmge/vs-next');
    assert.equal(CMS_VS_NEETPG.path, '/cms/vs-neet-pg');
    assert.equal(NEETPG_VS_USMLE.path, '/neet-pg/vs-usmle');
    const negative = CMS_VS_NEETPG.rows.find((r) => r.label === 'Negative marking');
    assert.match(negative.examB, /−1/, 'NEET PG has negative marking');
    assert.doesNotMatch(JSON.stringify(CMS_VS_NEETPG), /960|1060|4 marks × 240/);
});

function walk(dir) {
    return readdirSync(dir).flatMap((name) => {
        const p = path.join(dir, name);
        return statSync(p).isDirectory() ? walk(p) : [p];
    });
}

test('tool, /cms/salary and /cms/exam-pattern canonicals point at their own URL', () => {
    const toolDir = path.join(SRC, 'app/tools');
    for (const dir of readdirSync(toolDir)) {
        const file = path.join(toolDir, dir, 'page.tsx');
        if (!existsSync(file)) continue;
        const src = readFileSync(file, 'utf8');
        const slug = src.match(/const slug = '([^']+)'/)[1];
        assert.equal(slug, dir, `${dir} slug`);
        assert.match(src, /buildGuideMetadata\(\{ title, description, slug, path: `\/tools\/\$\{slug\}` \}\)/, `${dir} passes /tools path`);
    }
    assert.match(read('src/app/cms/salary/page.tsx'), /path: '\/cms\/salary'/);
    assert.match(read('src/app/cms/exam-pattern/page.tsx'), /path: '\/cms\/exam-pattern'/);
});

test('JSON-LD is rendered as plain <script> (server HTML), never next/script beforeInteractive', () => {
    const offenders = walk(SRC)
        .filter((f) => /\.(tsx|ts)$/.test(f))
        .filter((f) => /<Script[^>]*application\/ld\+json/s.test(readFileSync(f, 'utf8')));
    assert.deepEqual(offenders.map((f) => path.relative(FRONTEND, f)), []);
    assert.equal(jsonLdString({ a: '</script><script>alert(1)</script>' }).includes('</script>'), false);
});

test('root layout: no canonical/hreflang leak, no placeholder GSC token, no self-review markup', () => {
    const layout = read('src/app/layout.tsx');
    assert.doesNotMatch(layout, /alternates:\s*\{/);
    assert.doesNotMatch(layout, /REPLACE_WITH_GSC_VERIFICATION_TOKEN/);
    assert.doesNotMatch(layout, /CriticReview|MedicalWebPage|"FAQPage"|price: "199"/);
    assert.match(layout, /gtag\('consent', 'default'/);
    // GA library is only fetched after analytics consent
    assert.doesNotMatch(layout, /src=\{`https:\/\/www\.googletagmanager\.com\/gtag\/js/);
    assert.match(read('src/app/page.tsx'), /canonical: '\/'/);
    assert.equal(softwareAppSchema().aggregateRating, undefined, 'no self-awarded rating');
    assert.equal(websiteSchema().potentialAction, undefined, 'no SearchAction to a URL that ignores the query');
});

test('landing page sells only real plans; no fake reviews, toppers or activity counters', () => {
    const landing = read('src/app/_landing/LandingPage.tsx');
    assert.doesNotMatch(landing, /₹199|₹10,000|Premium Pass|Launch Offer|Verified PG Resident|2,900\+ active|Dr\. Riya Sharma|Dr\. Aarav Mehta|3,300\+/);
    assert.match(landing, /PREMIUM_PLANS/);
    assert.doesNotMatch(landing, /<footer/, 'global Footer is the only contentinfo');
    assert.match(landing, /function DemoTimer/);
    assert.doesNotMatch(read('src/components/ExamLandingLayout.tsx'), /47,000\+|price: '199'|Offline-friendly/);
    for (const page of ['ini-cet', 'usmle', 'fmge', 'medical-officer']) {
        assert.doesNotMatch(read(`src/app/${page}/page.tsx`), /4\.[78]\/5|47k\+|12,000\+|10,000\+|8,000\+|6,000\+|state-specific filters/, page);
    }
    const sub = read('src/app/subscription/page.tsx');
    assert.doesNotMatch(sub, /teacher consultations|Faculty Doubt|Video lecture archives|300 monthly credits|originalPrice|Simulate writing rich AI/);
});

test('PYQ year pages: no named toppers / AIR claims; subject split and cutoffs from shared data', () => {
    assert.doesNotMatch(read('src/lib/pyqYearData.ts'), /AIR-\d|\/960/);
    for (const year of getAllCmsYears()) {
        const y = getCmsYear(year);
        assert.equal(y.toppers.length, 0);
        assert.equal(y.topSubjects.reduce((a, s) => a + s.count, 0), y.totalQuestions);
        if (y.cutoffGeneral) assert.ok(y.cutoffGeneral <= 500);
    }
    assert.equal(getCmsYear(2024).cutoffGeneral, 305, 'same 2024 figure as /cms/cutoff/2024');
});

test('titles do not repeat the brand; question-bank CTAs use parameters the bank reads', () => {
    assert.equal(stripBrandSuffix('UPSC CMS Preparation 2026 | CrackCMS'), 'UPSC CMS Preparation 2026');
    assert.equal(stripBrandSuffix('Cookie Policy — CrackCMS'), 'Cookie Policy');
    assert.equal(stripBrandSuffix('No brand here'), 'No brand here');
    assert.equal(questionBankHref('neet-pg'), '/questions?exam=neet-pg');
    assert.equal(questionBankHref('cms', { year: 2024 }), '/questions/practice?exam=cms&year=2024');
    assert.equal(questionBankHref('neet-pg', { year: 2021 }), '/questions/neet-pg/practice?year=2021');
    for (const file of ['src/components/PyqYearLandingLayout.tsx', 'src/components/SubjectHubLayout.tsx', 'src/components/CutoffLayout.tsx', 'src/components/StrategyLayout.tsx', 'src/components/exams/ExamMicrosite.tsx', 'src/app/exams/_data.ts']) {
        assert.doesNotMatch(read(file), /exam_type=|toUpperCase\(\)|exam=CMS/, file);
    }
});

test('/exams/<unknown> is a real 404 and the duplicate routes redirect', () => {
    assert.match(read('src/app/exams/[slug]/page.tsx'), /notFound\(\)/);
    assert.match(read('src/app/inicet/page.tsx'), /permanentRedirect\('\/ini-cet'\)/);
    assert.match(read('src/app/neet-pg/vs-upsc-cms/page.tsx'), /permanentRedirect\('\/cms\/vs-neet-pg'\)/);
    assert.doesNotMatch(read('src/app/exams/layout.tsx'), /alternates/);
});
