/**
 * Partner ads stay isolated from the signed-in app.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/partner-ads.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const read = (rel: string) => readFileSync(join(root, rel), 'utf-8');

test('the ad iframe sandbox never grants same-origin or top-level navigation', () => {
    const source = read('src/components/PartnerAd.tsx');
    const match = source.match(/PARTNER_AD_SANDBOX = '([^']+)'/);
    assert.ok(match, 'PARTNER_AD_SANDBOX constant present');
    const tokens = match![1].split(/\s+/);
    assert.ok(tokens.includes('allow-scripts'));
    assert.ok(!tokens.includes('allow-same-origin'), 'same-origin would expose sign-in tokens');
    assert.ok(!tokens.some((t) => t.startsWith('allow-top-navigation')), 'ads must not navigate the page');
    assert.match(source, /sandbox=\{PARTNER_AD_SANDBOX\}/);
});

test('popunder / social-bar scripts are not loaded anywhere', () => {
    for (const rel of ['public/ads/native.html', 'public/ads/banner-160x300.html', 'src/components/PartnerAd.tsx']) {
        assert.doesNotMatch(read(rel), /abscloud\.org|bauval\.org\/14\//, rel);
    }
});

test('vercel.json keeps the strict headers on every non-ad path and frames ads only from this site', () => {
    const cfg = JSON.parse(read('vercel.json')) as {
        headers: { source: string; headers: { key: string; value: string }[] }[];
    };
    const strict = cfg.headers.find((r) => r.source === '/((?!ads/).*)');
    const ads = cfg.headers.find((r) => r.source === '/ads/(.*)');
    assert.ok(strict && ads);
    const get = (rule: typeof strict, key: string) => rule!.headers.find((h) => h.key === key)?.value || '';
    assert.equal(get(strict, 'X-Frame-Options'), 'DENY');
    assert.match(get(strict, 'Content-Security-Policy'), /default-src 'self'/);
    assert.equal(get(ads, 'X-Frame-Options'), 'SAMEORIGIN');
    assert.match(get(ads, 'Content-Security-Policy'), /frame-ancestors 'self'/);
    assert.match(get(ads, 'X-Robots-Tag'), /noindex/);

    const strictSource = new RegExp(`^${strict!.source}$`);
    for (const path of ['/', '/login', '/dashboard', '/admin', '/blog/x', '/adsense-info']) {
        assert.ok(strictSource.test(path), `strict headers cover ${path}`);
    }
    assert.ok(!strictSource.test('/ads/native.html'));
});
