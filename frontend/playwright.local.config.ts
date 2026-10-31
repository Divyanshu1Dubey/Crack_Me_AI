/**
 * End-to-end suite for the LOCAL stack (restored backup + local auth + mock
 * payments + offline AI). Start the stack first:
 *   powershell -ExecutionPolicy Bypass -File scripts\local\start-local.ps1 -Frontend prod
 * then, from frontend/:
 *   npx playwright test -c playwright.local.config.ts
 *
 * Specs live in tests/e2e/local/*.e2e.ts so the default config (which
 * matches *.spec.ts) never picks them up, and vice versa.
 */
import { defineConfig, devices } from '@playwright/test';

const out = process.env.E2E_OUTPUT_DIR || 'test-results/local';

export default defineConfig({
    testDir: './tests/e2e/local',
    testMatch: '**/*.e2e.ts',
    outputDir: `${out}/artifacts`,
    timeout: 120_000,
    expect: { timeout: 20_000 },
    fullyParallel: false,
    workers: 1,
    retries: 0,
    reporter: [
        ['list'],
        ['json', { outputFile: `${out}/results.json` }],
        ['html', { outputFolder: `${out}/html`, open: 'never' }],
    ],
    use: {
        baseURL: process.env.BASE_URL || 'http://localhost:3000',
        trace: 'retain-on-failure',
        screenshot: 'on',
        video: 'retain-on-failure',
        actionTimeout: 20_000,
        navigationTimeout: 60_000,
    },
    projects: [
        { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
        { name: 'tablet', use: { ...devices['Desktop Chrome'], viewport: { width: 820, height: 1180 }, hasTouch: true } },
        { name: 'mobile', use: { ...devices['Pixel 5'] } },
    ],
});
