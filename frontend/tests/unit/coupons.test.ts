/**
 * Coupon codes (2026-11-07): pure helpers (src/lib/couponRules.ts) and the wiring of /subscription,
 * /admin/coupons and the order call. Prices are computed by the server only (accounts/coupons.py).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/coupons.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    couponErrorMessage, couponFromSearch, couponShareLink, describeDiscount, isoToLocalInput, localInputToIso,
    looksLikeCouponCode, normalizeCouponCode,
} from '../../src/lib/couponRules.ts';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel: string) => readFileSync(path.join(ROOT, rel), 'utf8');

test('codes are compared upper case without spaces; links carry only well-formed codes', () => {
    assert.equal(normalizeCouponCode(' save 20 '), 'SAVE20');
    assert.equal(looksLikeCouponCode('cl-ab12cd34'), true);
    assert.equal(looksLikeCouponCode('x'), false);
    assert.equal(looksLikeCouponCode('bad_code!'), false);
    assert.equal(couponFromSearch('?coupon=anatomy50&x=1'), 'ANATOMY50');
    assert.equal(couponFromSearch('?coupon=%3Cscript%3E'), '');
    assert.equal(couponFromSearch(''), '');
    assert.equal(couponShareLink('https://www.cracklabs.app/', 'SAVE20'), 'https://www.cracklabs.app/subscription?coupon=SAVE20');
});

test('discounts read as people say them', () => {
    assert.equal(describeDiscount('percent', 20), '20% off');
    assert.equal(describeDiscount('fixed', 100), '₹100 off');
});

test('refusals show the server sentence; field errors and rate limits are readable', () => {
    assert.equal(couponErrorMessage({ response: { status: 400, data: { code: 'coupon_expired', error: 'This coupon code has expired.' } } }),
        'This coupon code has expired.');
    assert.equal(couponErrorMessage({ response: { status: 400, data: { errors: { discount_value: 'Whole number from 1 to 100.' } } } }),
        'discount value: Whole number from 1 to 100.');
    assert.equal(couponErrorMessage({ response: { status: 429, data: {} } }), 'Too many coupon checks. Please wait a while and try again.');
    assert.equal(couponErrorMessage(new Error('Network Error')), 'The coupon could not be checked. Please try again.');
});

test('datetime-local values round-trip through ISO', () => {
    assert.equal(localInputToIso(''), null);
    const iso = localInputToIso('2026-12-31T23:59');
    assert.ok(iso && !Number.isNaN(Date.parse(iso)));
    assert.equal(isoToLocalInput(iso), '2026-12-31T23:59');
    assert.equal(isoToLocalInput(null), '');
});

test('the order call carries the code and /subscription handles a free activation', () => {
    assert.match(read('src/lib/api.ts'), /coupon_code: couponCode \|\| undefined/);
    const page = read('src/app/subscription/page.tsx');
    assert.match(page, /authAPI\.subscribeOrder\(plan, requestId, couponCode\)/);
    assert.match(page, /orderRes\.data\?\.free_activation/);
    assert.match(page, /Have a coupon code\?/);
    assert.match(page, /couponFromSearch\(window\.location\.search\)/);
    // The scholarship rate is never combined with a code.
    assert.match(page, /plan === 'scholarship_1_month' \? undefined/);
});

test('admins reach the coupons page from the sidebar', () => {
    assert.match(read('src/components/Sidebar.tsx'), /href: '\/admin\/coupons', label: 'Coupon Codes'/);
    assert.match(read('src/app/admin/coupons/page.tsx'), /couponsAPI\.adminRedemptions/);
    assert.match(read('src/lib/appShellRoutes.ts'), /'\/admin\/coupons': 'Coupon Codes'/);
});
