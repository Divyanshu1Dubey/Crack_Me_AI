import { test, expect } from '@playwright/test';

/**
 * Regression (2026-11-03, NEXT_PUBLIC_AUTH_MODE=django): after signing in through the form, every
 * protected link (Question Bank, Tests, ...) led back to /login although the session was valid.
 * The App Router had cached the middleware's redirect to /login for the links it prefetched while
 * the visitor was still signed out, and the login page navigated client-side, so the cache
 * survived. Fixed by a full page load after sign-in / sign-out (lib/authNavigation.ts) and by never
 * redirecting prefetches (utils/supabase/middleware.ts).
 *
 * Needs a django-mode build in front of a backend with AUTH_PROVIDER=django and a verified test
 * account (never a real user's credentials):
 *   E2E_SIGNIN_EMAIL=... E2E_SIGNIN_PASSWORD=... PLAYWRIGHT_SKIP_WEBSERVER=1 BASE_URL=http://localhost:3000 \
 *     npx playwright test tests/e2e/signin-navigation.spec.ts --project=chromium
 */
const email = process.env.E2E_SIGNIN_EMAIL || '';
const password = process.env.E2E_SIGNIN_PASSWORD || '';

test.skip(!email || !password, 'set E2E_SIGNIN_EMAIL / E2E_SIGNIN_PASSWORD (a test account) to run');

test('after signing in, protected links open their page instead of /login', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('input[type="email"]', { timeout: 60000 });
  // Give the router time to prefetch the visible protected links while signed out.
  await page.waitForTimeout(2000);
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(dashboard|admin)(\?|$)/, { timeout: 60000 });

  // Client-side navigation to a protected route prefetched while signed out.
  await page.locator('a[href="/questions"]:visible').first().click();
  await expect(page).toHaveURL(/\/questions(\?|$)/, { timeout: 30000 });

  // And a full load of a protected route keeps the session.
  await page.goto('/tests', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/tests(\?|$)/, { timeout: 30000 });
});
