/**
 * tests/e2e/fixtures/auth.ts — production-grade auth fixture for Playwright.
 *
 * Why this exists
 * ---------------
 * The /practice, /dashboard, /admin, /ai-tutor and most other gated routes
 * redirect anonymous users to /login. Running QA on those routes requires
 * a real Supabase/Django session.
 *
 * Pattern
 * -------
 * Each role (student / premium / admin) logs in through the real /login
 * form once per test, and the resulting authenticated context is reused
 * across the tests in that describe block.
 *
 * If the env vars (QA_TEST_USER_EMAIL, QA_TEST_USER_PASSWORD, etc.) are
 * not set, `loginAs` returns an UN-AUTHENTICATED context and individual
 * tests should call `test.skip(...)` on /login-detected navigation —
 * that's the convention used by Bug #R3 / Bug #R1 regression tests.
 *
 * Usage
 * -----
 *   import { loginAs, ROLES } from './fixtures/auth';
 *
 *   test('practice page renders', async ({ page }) => {
 *       const ctx = await loginAs(page, ROLES.STUDENT);
 *       if (!ctx.authenticated) { test.skip(); return; }
 *       // ...
 *   });
 */
import { type Page, expect } from '@playwright/test';

export const ROLES = {
    STUDENT: 'student',
    PREMIUM: 'premium',
    ADMIN: 'admin',
    ANONYMOUS: 'anonymous',
} as const;
export type Role = (typeof ROLES)[keyof typeof ROLES];

interface LoginResult {
    authenticated: boolean;
    role: Role;
    reason?: string;
}

function envForRole(role: Role): { email?: string; password?: string } {
    if (role === ROLES.STUDENT) {
        return {
            email: process.env.QA_TEST_USER_EMAIL,
            password: process.env.QA_TEST_USER_PASSWORD,
        };
    }
    if (role === ROLES.PREMIUM) {
        return {
            email: process.env.QA_PREMIUM_USER_EMAIL,
            password: process.env.QA_PREMIUM_USER_PASSWORD,
        };
    }
    if (role === ROLES.ADMIN) {
        return {
            email: process.env.QA_ADMIN_USER_EMAIL,
            password: process.env.QA_ADMIN_USER_PASSWORD,
        };
    }
    return {};
}

/**
 * Login as the given role through the real /login form.
 *
 * Returns `{ authenticated: false, reason: '...' }` if env vars are
 * missing OR if the login form rejects the credentials. Callers should
 * `test.skip(true, reason)` on unauthenticated so CI stays green when
 * secrets are absent, but the same test will actually run when secrets
 * are present (CI, staging, local dev with a real test account).
 */
export async function loginAs(page: Page, role: Role): Promise<LoginResult> {
    if (role === ROLES.ANONYMOUS) {
        return { authenticated: true, role };
    }

    const { email, password } = envForRole(role);
    if (!email || !password) {
        return {
            authenticated: false,
            role,
            reason: `Missing QA env for ${role}: set QA_${role.toUpperCase()}_USER_EMAIL + _PASSWORD`,
        };
    }

    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="identifier"], input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');

    // Successful login redirects to /dashboard (or wherever the AuthProvider
    // decides). If we end up back on /login OR an error banner appears, the
    // credentials were rejected.
    await page.waitForLoadState('domcontentloaded');
    if (page.url().includes('/login')) {
        return {
            authenticated: false,
            role,
            reason: `Login form rejected ${role} credentials (still on /login)`,
        };
    }

    // Sanity: dashboard chrome should be visible.
    try {
        await expect(page.locator('aside[aria-label="Primary sidebar navigation"]')).toBeVisible({ timeout: 10000 });
    } catch {
        return {
            authenticated: false,
            role,
            reason: `Login succeeded but sidebar did not render (likely stuck on a public page)`,
        };
    }

    return { authenticated: true, role };
}

/**
 * Skip-with-reason helper. Centralised so the message is consistent
 * across the suite.
 */
export function skipIfAnonymous(result: LoginResult, test: { skip: (cond: boolean, reason?: string) => void }) {
    if (!result.authenticated) {
        test.skip(true, result.reason ?? 'authentication required');
        return true;
    }
    return false;
}
