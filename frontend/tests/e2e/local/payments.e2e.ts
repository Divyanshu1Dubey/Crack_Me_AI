/**
 * Payments (PAYMENTS_MODE=mock: no network, no money). The mock replaces only
 * Razorpay's order API and checkout popup; signature verification, the
 * webhook, activation, stacking and entitlement run the real code.
 *
 * Signatures are computed with the local stack's mock secrets from
 * backend/.env.localdev (never logged).
 */
import { expect, test, type APIRequestContext } from '@playwright/test';
import crypto from 'node:crypto';
import { API, api, apiLogin, apiRegister, expectNoHorizontalOverflow, hmacHex, isProject, localEnv, prepareBrowser, profile, rowsOf, SEED, snap, watchPage, type Session } from './support';

type Row = Record<string, any>;
const rid = () => `e2e-${Date.now().toString(36)}-${crypto.randomBytes(3).toString('hex')}`;

async function order(request: APIRequestContext, session: Session, plan: string) {
    return api(request, session, 'POST', '/auth/subscribe/order/', { plan, request_id: rid() });
}

function signed(orderId: string, paymentId = `pay_e2e_${crypto.randomBytes(6).toString('hex')}`) {
    return {
        razorpay_order_id: orderId,
        razorpay_payment_id: paymentId,
        razorpay_signature: hmacHex(localEnv('RAZORPAY_KEY_SECRET'), `${orderId}|${paymentId}`),
    };
}

async function status(request: APIRequestContext, session: Session): Promise<Row> {
    const res = await api(request, session, 'GET', '/auth/subscribe/status/');
    expect(res.status, 'subscription status').toBe(200);
    return res.body;
}

async function webhook(request: APIRequestContext, payload: unknown, signature?: string) {
    const body = JSON.stringify(payload);
    const res = await request.post(`${API}/auth/subscribe/webhook/`, {
        data: body,
        headers: {
            'Content-Type': 'application/json',
            'X-Razorpay-Signature': signature ?? hmacHex(localEnv('RAZORPAY_WEBHOOK_SECRET'), body),
        },
    });
    let json: Row | null = null;
    try { json = await res.json(); } catch { json = null; }
    return { status: res.status(), body: json };
}

const captured = (orderId: string, paymentId: string) => ({
    event: 'payment.captured',
    payload: { payment: { entity: { id: paymentId, order_id: orderId, status: 'captured' } } },
});

/** A question the free tier cannot open (for entitlement checks). */
async function lockedQuestionId(request: APIRequestContext, session: Session): Promise<number> {
    const res = await api(request, session, 'GET', '/questions/?exam_type=cms&page_size=100');
    const q = rowsOf<Row>(res.body).find(r => r.is_showcase === false);
    expect(q, 'a non-showcase question').toBeTruthy();
    return q!.id;
}

test.describe('payments (mock provider)', () => {
    test('a free student buys the 1-month pass through checkout and gets premium', async ({ page, request }, testInfo) => {
        const session = await apiRegister(request, 'buyer');
        const locked = await lockedQuestionId(request, session);
        expect([402, 403, 404]).toContain((await api(request, session, 'GET', `/questions/${locked}/`)).status);

        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto('/subscription');
        const buy = page.getByRole('button', { name: /unlock monthly access/i });
        await expect(buy).toBeVisible({ timeout: 60_000 });
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'subscription-free');
        await buy.click();
        await expect(page.getByText(/your active plan/i).first()).toBeVisible({ timeout: 60_000 });
        await snap(page, testInfo, 'subscription-active');

        const st = await status(request, session);
        expect(st.is_subscribed).toBe(true);
        expect(st.subscription?.plan).toBe('1_month');
        expect(st.subscription?.days_remaining).toBeGreaterThanOrEqual(29);
        // Entitlement follows the subscription: the locked question opens with its key.
        const after = await api(request, session, 'GET', `/questions/${locked}/`);
        expect(after.status).toBe(200);
        expect(String(after.body?.correct_answer || '')).toMatch(/^[A-D]?$/);
        watch.expectClean();
    });

    test.describe('server-side payment rules', () => {
        test.beforeEach(({}, testInfo) => {
            test.skip(!isProject(testInfo, 'desktop'), 'API-level checks run once (desktop)');
        });

        test('invalid signature, foreign order, unknown or lifetime plan are refused', async ({ request }) => {
            const alice = await apiRegister(request, 'pay-a');
            const bob = await apiRegister(request, 'pay-b');

            const o = await order(request, alice, '1_month');
            expect(o.status, JSON.stringify(o.body)).toBe(200);
            expect(o.body.amount).toBe(12900);

            const bad = { ...signed(o.body.order_id), razorpay_signature: 'f'.repeat(64) };
            const badRes = await api(request, alice, 'POST', '/auth/subscribe/verify/', bad);
            expect(badRes.status).toBe(400);
            expect((await status(request, alice)).is_subscribed).toBe(false);

            const foreign = await api(request, bob, 'POST', '/auth/subscribe/verify/', signed(o.body.order_id));
            expect(foreign.status).toBe(403);
            expect((await status(request, bob)).is_subscribed).toBe(false);

            for (const plan of ['legacy', 'lifetime', 'free', '']) {
                const r = await order(request, alice, plan);
                expect(r.status, `plan "${plan}"`).toBe(400);
            }
            // Scholarship pricing needs a passed scholarship test.
            expect((await order(request, alice, 'scholarship_1_month')).status).toBe(403);
            // Missing fields
            expect((await api(request, alice, 'POST', '/auth/subscribe/verify/', { razorpay_order_id: o.body.order_id })).status).toBe(400);
        });

        test('verify is idempotent and purchases stack without double credit', async ({ request }) => {
            const user = await apiRegister(request, 'stack');
            const o1 = await order(request, user, '1_month');
            const pay1 = signed(o1.body.order_id);
            const v1 = await api(request, user, 'POST', '/auth/subscribe/verify/', pay1);
            expect(v1.status, JSON.stringify(v1.body)).toBe(200);
            const s1 = await status(request, user);
            expect(s1.is_subscribed).toBe(true);
            const expiry1 = Date.parse(s1.subscription.expires_at);

            // Replay of the same verified payment: success, no extra period.
            const replay = await api(request, user, 'POST', '/auth/subscribe/verify/', pay1);
            expect(replay.status).toBe(200);
            // The same order with a different payment id must not credit again.
            const second = await api(request, user, 'POST', '/auth/subscribe/verify/', signed(o1.body.order_id));
            expect(second.status).toBeLessThan(500);
            const s1b = await status(request, user);
            expect(Math.abs(Date.parse(s1b.subscription.expires_at) - expiry1)).toBeLessThan(60_000);

            // A real second purchase stacks on the remaining time (~30 + 90 days).
            const o2 = await order(request, user, '3_months');
            expect(o2.status).toBe(200);
            expect(o2.body.amount).toBe(44900);
            expect((await api(request, user, 'POST', '/auth/subscribe/verify/', signed(o2.body.order_id))).status).toBe(200);
            const s2 = await status(request, user);
            const days = (Date.parse(s2.subscription.expires_at) - Date.now()) / 86_400_000;
            expect(days).toBeGreaterThan(115);
            expect(days).toBeLessThan(125);

            const history = await api(request, user, 'GET', '/auth/subscribe/history/');
            expect(history.status).toBe(200);
        });

        test('webhook activates once, ignores duplicates, bad signatures and other events', async ({ request }) => {
            const user = await apiRegister(request, 'hook');
            const o = await order(request, user, '1_month');
            const paymentId = `pay_e2e_${crypto.randomBytes(6).toString('hex')}`;

            const forged = await webhook(request, captured(o.body.order_id, paymentId), 'deadbeef');
            expect(forged.status).toBe(400);
            expect((await status(request, user)).is_subscribed).toBe(false);

            const first = await webhook(request, captured(o.body.order_id, paymentId));
            expect(first.status, JSON.stringify(first.body)).toBe(200);
            expect(first.body?.status).toBe('activated');
            const s1 = await status(request, user);
            expect(s1.is_subscribed).toBe(true);

            const dup = await webhook(request, captured(o.body.order_id, paymentId));
            expect(dup.body?.status).toBe('already_processed');
            const otherPayment = await webhook(request, captured(o.body.order_id, `pay_e2e_${crypto.randomBytes(6).toString('hex')}`));
            expect(otherPayment.body?.status).toBe('already_processed');
            // The browser's verify arriving after the webhook does not stack a second period.
            expect((await api(request, user, 'POST', '/auth/subscribe/verify/', signed(o.body.order_id, paymentId))).status).toBe(200);
            const s2 = await status(request, user);
            expect(Math.abs(Date.parse(s2.subscription.expires_at) - Date.parse(s1.subscription.expires_at))).toBeLessThan(60_000);

            // Refund events are not handled automatically (documented owner action).
            const refund = await webhook(request, { event: 'refund.processed', payload: { refund: { entity: { payment_id: paymentId } } } });
            expect(refund.body?.status).toBe('ignored');
        });

        test('admin revoke removes premium access; admin lifetime grant restores it', async ({ request }) => {
            const admin = await apiLogin(request, SEED.admin);
            const user = await apiRegister(request, 'revoke');
            const me = await profile(request, user);
            const o = await order(request, user, '1_month');
            expect((await api(request, user, 'POST', '/auth/subscribe/verify/', signed(o.body.order_id))).status).toBe(200);
            const locked = await lockedQuestionId(request, user);
            expect((await api(request, user, 'GET', `/questions/${locked}/`)).status).toBe(200);

            // Students cannot use the admin endpoint.
            expect((await api(request, user, 'POST', `/auth/admin/users/${me.id}/subscription/`, { action: 'grant', plan: 'legacy' })).status).toBe(403);

            const revoke = await api(request, admin, 'POST', `/auth/admin/users/${me.id}/subscription/`, { action: 'revoke' });
            expect(revoke.status, JSON.stringify(revoke.body)).toBe(200);
            expect((await status(request, user)).is_subscribed).toBe(false);
            expect([402, 403, 404]).toContain((await api(request, user, 'GET', `/questions/${locked}/`)).status);

            const grant = await api(request, admin, 'POST', `/auth/admin/users/${me.id}/subscription/`, { action: 'grant', plan: 'legacy' });
            expect(grant.status, JSON.stringify(grant.body)).toBe(200);
            const st = await status(request, user);
            expect(st.is_subscribed).toBe(true);
            expect(st.subscription?.expires_at ?? null).toBeNull();
            expect((await api(request, user, 'GET', `/questions/${locked}/`)).status).toBe(200);
            // What the server does when a lifetime member starts another purchase
            // (the UI hides the buy buttons for them); recorded for the report.
            const extra = await order(request, user, '1_month');
            expect(extra.status).toBeLessThan(500);
            test.info().annotations.push({ type: 'lifetime-member-order-status', description: String(extra.status) });
        });

        test('AI entitlement follows the plan: capped tutor for free, uncapped for premium', async ({ request }) => {
            const free = await profile(request, await apiRegister(request, 'wallet'));
            const premium = await profile(request, await apiLogin(request, SEED.premium));
            expect(free.is_premium).toBe(false);
            expect(typeof free.ai_tutor_daily_cap).toBe('number');
            expect(premium.is_premium).toBe(true);
            expect(premium.ai_tutor_daily_cap ?? null).toBeNull();
        });
    });
});
