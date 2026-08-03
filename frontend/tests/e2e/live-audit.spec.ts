/**
 * LIVE AUDIT — Playwright walk of /questions/neet-pg/practice and
 * /questions/inicet/practice on cracklabs.app.  Records every
 * console error, failed request, missing option/anomaly on the
 * first 30 questions of each exam, and writes a single
 * bug-report.json blob.
 *
 * No credentials are hardcoded in source — they are passed via
 * environment variables (LIVE_AUDIT_EMAIL / LIVE_AUDIT_PASSWORD).
 */
import { test, expect, type Page, type Request as PWRequest } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = process.env.LIVE_AUDIT_BASE_URL || 'https://cracklabs.app';
const EMAIL = process.env.LIVE_AUDIT_EMAIL || '';
const PASSWORD = process.env.LIVE_AUDIT_PASSWORD || '';
const REPORT_PATH = path.join(process.cwd(), 'tests/e2e/.audit', 'bug-report.json');

interface Bug {
  id: string;
  exam: 'neet-pg' | 'inicet';
  category: string;
  questionIndex?: number;
  description: string;
  evidence: Record<string, unknown>;
}

async function attachBugSink(page: Page, exam: 'neet-pg' | 'inicet') {
  const bugs: Bug[] = [];
  const consoleErrors: { text: string; location: string | null }[] = [];
  const failedRequests: { url: string; status: number; method: string }[] = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({ text: msg.text(), location: msg.location()?.url || null });
    }
  });
  page.on('requestfailed', (req: PWRequest) => {
    failedRequests.push({
      url: req.url(),
      status: req.failure()?.errorCode ? 0 : 0,
      method: req.method(),
    });
  });
  page.on('response', async (resp) => {
    const status = resp.status();
    if (status >= 400) {
      failedRequests.push({ url: resp.url(), status, method: resp.request().method() });
    }
  });

  const addBug = (b: Omit<Bug, 'exam'>) => {
    bugs.push({ ...b, exam });
  };

  return { bugs, consoleErrors, failedRequests, addBug };
}

async function loginIfNeeded(page: Page) {
  if (!EMAIL || !PASSWORD) throw new Error('LIVE_AUDIT_EMAIL / LIVE_AUDIT_PASSWORD not set');
  await page.goto(`${BASE_URL}/login`);
  await page.locator('input[name="email"], input[type="email"], input#email').first().fill(EMAIL);
  await page.locator('input[name="password"], input[type="password"], input#password').first().fill(PASSWORD);
  await page.getByRole('button', { name: /log in|sign in|login/i }).first().click();
  await page.waitForURL(/\/(dashboard|admin|questions)/, { timeout: 30_000 });
}

async function inspectQuestion(page: Page, exam: 'neet-pg' | 'inicet', idx: number, sink: ReturnType<typeof attachBugSink> extends Promise<infer R> ? R : never) {
  // The exact data-testid depends on the player; we look for option buttons
  // by aria-label pattern "Option A", "Option B", etc.
  const optionRe = /option\s+[abcd]/i;
  const optionBtns = page.getByRole('button').filter({ hasText: optionRe });
  const optionCount = await optionBtns.count();

  if (optionCount === 0) {
    sink.addBug({
      id: `no-options-${idx}`,
      category: 'missing-options',
      questionIndex: idx,
      description: 'Question rendered with zero A/B/C/D option buttons',
      evidence: { url: page.url() },
    });
  } else if (optionCount < 4) {
    sink.addBug({
      id: `partial-options-${idx}`,
      category: 'partial-options',
      questionIndex: idx,
      description: `Question rendered with only ${optionCount} of 4 option buttons`,
      evidence: { url: page.url(), count: optionCount },
    });
  }

  // If options exist, try to interact and see what happens
  if (optionCount > 0) {
    const firstBtn = optionBtns.first();
    await firstBtn.click({ timeout: 5_000, trial: false }).catch(() => undefined);
    // Wait for either explanation card or AI Tutor button
    await page.waitForTimeout(1500);
    const explCount = await page.locator('[data-testid="expl-why-correct"]').count();
    if (explCount === 0) {
      sink.addBug({
        id: `no-explanation-${idx}`,
        category: 'missing-explanation',
        questionIndex: idx,
        description: 'After answering, no "Why correct" explanation card appeared',
        evidence: { url: page.url() },
      });
    }
  }

  // Check for next-question button & progress
  const nextBtn = page.getByRole('button', { name: /next|next question/i }).first();
  const nextAvailable = await nextBtn.isVisible().catch(() => false);
  return { optionCount, nextAvailable };
}

async function walkExam(page: Page, exam: 'neet-pg' | 'inicet', limit: number) {
  const url = `${BASE_URL}/questions/${exam}/practice`;
  const sink = await attachBugSink(page, exam);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60_000 });
  await page.waitForTimeout(2_000);

  // Some pages need a "Start practice" click
  const startBtn = page.getByRole('button', { name: /start|begin|next/i }).first();
  if (await startBtn.isVisible().catch(() => false)) {
    await startBtn.click().catch(() => undefined);
    await page.waitForTimeout(1500);
  }

  for (let i = 0; i < limit; i++) {
    await inspectQuestion(page, exam, i, sink);
    // Advance to next question
    const nextBtn = page.getByRole('button', { name: /next|next question/i }).first();
    if (!(await nextBtn.isVisible().catch(() => false))) break;
    await nextBtn.click().catch(() => undefined);
    await page.waitForTimeout(800);
  }

  return sink;
}

test('LIVE AUDIT — NEET-PG + INI-CET practice (console + network + 30 questions)', async ({ page }) => {
  test.setTimeout(600_000);
  await loginIfNeeded(page);

  const neetPg = await walkExam(page, 'neet-pg', 15);
  const iniCet = await walkExam(page, 'inicet', 15);

  // Mobile viewport: same flow, 390 × 844
  await page.setViewportSize({ width: 390, height: 844 });
  const neetMobile = await walkExam(page, 'neet-pg', 5);
  const iniMobile = await walkExam(page, 'inicet', 5);

  const report = {
    baseUrl: BASE_URL,
    timestamp: new Date().toISOString(),
    neetPg: {
      bugs: neetPg.bugs,
      consoleErrors: neetPg.consoleErrors,
      failedRequests: neetPg.failedRequests,
    },
    iniCet: {
      bugs: iniCet.bugs,
      consoleErrors: iniCet.consoleErrors,
      failedRequests: iniCet.failedRequests,
    },
    mobile: {
      neetPg: { bugs: neetMobile.bugs, consoleErrors: neetMobile.consoleErrors, failedRequests: neetMobile.failedRequests },
      iniCet: { bugs: iniMobile.bugs, consoleErrors: iniMobile.consoleErrors, failedRequests: iniMobile.failedRequests },
    },
  };

  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));
  // eslint-disable-next-line no-console
  console.log(`\n\n=== AUDIT REPORT @ ${REPORT_PATH} ===\n${JSON.stringify(report, null, 2)}\n`);
});
