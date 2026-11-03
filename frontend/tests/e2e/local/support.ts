/**
 * Shared helpers for the local E2E suite (see playwright.local.config.ts).
 *
 * Accounts: the seeded local users (student@ / premium@ / admin@local.test,
 * password = LOCAL_SEED_PASSWORD in backend/.env.localdev, or E2E_SEED_PASSWORD)
 * and throwaway users created through the dev-only local register endpoint.
 * Nothing here talks to Supabase, Razorpay or any external service.
 */
import { expect, type APIRequestContext, type Page, type TestInfo } from '@playwright/test';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export const API = process.env.E2E_API_URL || 'http://127.0.0.1:8000/api';

export const SEED = {
    student: 'student@local.test',
    premium: 'premium@local.test',
    admin: 'admin@local.test',
} as const;

export interface Session {
    access: string;
    refresh: string;
    email: string;
    password: string;
    isAdmin: boolean;
}

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

const isAdminUser = (user: Record<string, unknown> | undefined) =>
    !!user && (user.is_admin === true || String(user.role || '').toLowerCase() === 'admin');

let localEnvCache: Record<string, string> | null = null;

/**
 * A value from backend/.env.localdev - the local stack's own mock secrets
 * (seed password, mock Razorpay keys). Never log what this returns.
 */
export function localEnv(key: string): string {
    if (!localEnvCache) {
        const envFile = path.resolve(__dirname, '../../../../backend/.env.localdev');
        localEnvCache = {};
        for (const raw of fs.readFileSync(envFile, 'utf8').split(/\r?\n/)) {
            const m = /^([A-Za-z0-9_]+)=(.*)$/.exec(raw.trim());
            if (m) localEnvCache[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
        }
    }
    return localEnvCache[key] || '';
}

export function seedPassword(): string {
    if (process.env.E2E_SEED_PASSWORD) return process.env.E2E_SEED_PASSWORD;
    const value = localEnv('LOCAL_SEED_PASSWORD');
    if (!value) throw new Error('LOCAL_SEED_PASSWORD missing from backend/.env.localdev');
    return value;
}

/** Hex HMAC-SHA256, the scheme Razorpay uses for payment and webhook signatures. */
export const hmacHex = (secret: string, payload: string) =>
    crypto.createHmac('sha256', secret).update(payload).digest('hex');

/** Rows of a DRF list response (paginated or not). */
export const rowsOf = <T = any>(body: any): T[] => (Array.isArray(body) ? body : body?.results ?? []);

/** The current user's profile (id, flags) from the backend. */
export async function profile(request: APIRequestContext, session: Session) {
    const res = await request.get(`${API}/auth/profile/`, { headers: { Authorization: `Bearer ${session.access}` } });
    expect(res.status(), 'profile').toBe(200);
    return res.json();
}

/** Log in through the dev-only API (fast path for tests that are not about login). */
export async function apiLogin(request: APIRequestContext, email: string, password = seedPassword()): Promise<Session> {
    const res = await request.post(`${API}/auth/local/login/`, { data: { email, password } });
    expect(res.status(), `local login for ${email}`).toBe(200);
    const body = await res.json();
    return { access: body.access, refresh: body.refresh, email, password, isAdmin: isAdminUser(body.user) };
}

let counter = 0;

/** Create a brand-new student through the dev-only register endpoint. */
export async function apiRegister(request: APIRequestContext, prefix = 'e2e'): Promise<Session> {
    counter += 1;
    const stamp = `${Date.now().toString(36)}${counter}${Math.floor(Math.random() * 1e4)}`;
    const email = `${prefix}-${stamp}@local.test`;
    const password = `E2e!${stamp}Pw9`;
    const res = await request.post(`${API}/auth/local/register/`, {
        data: { username: `${prefix}_${stamp}`, email, password, first_name: 'E2E', last_name: 'Tester' },
    });
    expect(res.status(), `local register ${email}: ${await res.text()}`).toBe(201);
    const body = await res.json();
    return { access: body.access, refresh: body.refresh, email, password, isAdmin: isAdminUser(body.user) };
}

/** Authenticated JSON call to the backend (for setup and DB-state verification). */
export async function api<T = any>(request: APIRequestContext, session: Session | null, method: 'GET' | 'POST' | 'PATCH' | 'DELETE', urlPath: string, data?: unknown): Promise<{ status: number; body: T }> {
    const res = await request.fetch(`${API}${urlPath}`, {
        method,
        data: data === undefined ? undefined : data,
        headers: session ? { Authorization: `Bearer ${session.access}` } : undefined,
    });
    let body: any = null;
    try { body = await res.json(); } catch { body = null; }
    return { status: res.status(), body };
}

/**
 * Seed browser storage before any page script runs: optional local session,
 * theme, and an essential-only cookie choice so the consent banner does not
 * cover the page (the privacy-preserving option).
 */
export async function prepareBrowser(page: Page, session: Session | null, theme: 'light' | 'dark' = 'light') {
    if (session) {
        // Presence cookies the middleware gates protected routes on (set by
        // lib/localAuth.ts after a real login; injected here with the tokens).
        await page.context().addCookies([
            { name: 'crack_local_session', value: '1', url: BASE_URL },
            ...(session.isAdmin ? [{ name: 'crack_local_admin', value: '1', url: BASE_URL }] : []),
        ]);
    }
    await page.addInitScript(({ tok, theme: t }) => {
        try {
            localStorage.setItem('theme', t);
            localStorage.setItem('crackcms_consent_v1', JSON.stringify({ essential: true, analytics: false, marketing: false, updated_at: new Date().toISOString() }));
            // Init scripts run on every navigation: seed the session only on the
            // tab's first load, so a logout inside the test stays logged out.
            if (tok && !sessionStorage.getItem('__e2e_session_seeded')) {
                localStorage.setItem('crack_local_access', tok.access);
                localStorage.setItem('crack_local_refresh', tok.refresh);
                sessionStorage.setItem('__e2e_session_seeded', '1');
            }
        } catch { /* storage unavailable */ }
    }, { tok: session ? { access: session.access, refresh: session.refresh } : null, theme });
}

/** Benign noise that is not an application failure. */
const DEFAULT_ALLOW: RegExp[] = [
    /favicon/i,
    /Download the React DevTools/i,
    /\[Fast Refresh\]/i,
    /third-party cookie/i,
];

/**
 * Collects console errors, uncaught page errors, failed requests and 5xx
 * responses for the lifetime of the page.
 */
export function watchPage(page: Page) {
    const problems: string[] = [];
    page.on('console', msg => {
        if (msg.type() === 'error') problems.push(`console.error: ${msg.text().slice(0, 300)}`);
    });
    page.on('pageerror', err => problems.push(`pageerror: ${err.message.slice(0, 300)}`));
    page.on('response', res => {
        if (res.status() >= 500) problems.push(`HTTP ${res.status()} ${res.request().method()} ${res.url()}`);
    });
    page.on('requestfailed', req => {
        const failure = req.failure()?.errorText || '';
        // Navigations abort in-flight requests; that is not a failure.
        if (/ERR_ABORTED|NS_BINDING_ABORTED/i.test(failure)) return;
        problems.push(`requestfailed: ${req.method()} ${req.url()} ${failure}`);
    });
    return {
        problems,
        expectClean(allow: RegExp[] = []) {
            const relevant = problems.filter(p => ![...DEFAULT_ALLOW, ...allow].some(rx => rx.test(p)));
            expect(relevant, `browser problems:\n${relevant.join('\n')}`).toEqual([]);
        },
    };
}

/** Fails when the page scrolls horizontally (layout overflow at this viewport). */
export async function expectNoHorizontalOverflow(page: Page) {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, 'horizontal overflow in px').toBeLessThanOrEqual(1);
}

/** Full-page screenshot attached to the report (and kept as an artifact). */
export async function snap(page: Page, testInfo: TestInfo, name: string) {
    const file = testInfo.outputPath(`${name}.png`);
    // CSS-pixel scale keeps phone captures (DPR 2.75) small enough to finish.
    await page.screenshot({ path: file, fullPage: true, scale: 'css', animations: 'disabled', timeout: 60_000 });
    await testInfo.attach(name, { path: file, contentType: 'image/png' });
}

export const isProject = (testInfo: TestInfo, ...names: string[]) => names.includes(testInfo.project.name);
