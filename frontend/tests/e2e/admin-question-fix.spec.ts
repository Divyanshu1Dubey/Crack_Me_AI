import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@cracklabs.app';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin-test-pw';

test('admin can fix a NEET PG question and the public page reflects it', async ({ page, request }) => {
  // Login via the admin page
  await page.goto('/admin/login');
  await page.getByLabel('Email').fill(ADMIN_EMAIL);
  await page.getByLabel('Password').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();

  // Open the editor with the NEET PG filter
  await page.goto('/admin/questions-editor');
  await page.getByRole('combobox', { name: 'Exam' }).selectOption('neet_pg');
  await page.getByRole('button', { name: /search/i }).click();

  // Open the first row
  const firstEdit = page.getByRole('button', { name: 'Edit' }).first();
  await firstEdit.click();

  // Replace the question text with a clean version
  const textarea = page.locator('textarea').first();
  await textarea.fill('Which of the following are components of the physical quality of life index (PQLI)? (FIXED)');

  // Save
  await page.getByRole('button', { name: /^Save$/ }).click();
  await expect(page.getByText(/Edit Question/)).toBeHidden({ timeout: 10_000 });

  // Verify the public page shows the fix
  await page.goto('/questions/neet-pg/practice');
  await expect(page.getByText('(FIXED)')).toBeVisible({ timeout: 15_000 });
});