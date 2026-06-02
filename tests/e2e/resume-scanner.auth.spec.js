const { test, expect } = require('@playwright/test');

test.describe('Frontend States', () => {

  test.beforeEach(async ({ request }) => {
    await request.post('/__reset');
  });

  test('shows auth screen when no token present', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /ai 履歷分析/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /google 登入/i })).toBeVisible();
  });

  test('shows upload zone after auth bypass @smoke', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });
    await page.goto('/');
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/支援 pdf 格式/i)).toBeVisible();
  });

  test('shows user email and usage badge after auth', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });
    await page.goto('/');
    await expect(page.locator('#navEmail')).toContainText('test@test.com');
    await expect(page.getByText(/7\/7/)).toBeVisible();
  });

  test('shows empty history state in sidebar', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });
    await page.goto('/');
    await expect(page.locator('#historyList').getByText(/尚無分析記錄/i)).toBeVisible({ timeout: 10000 });
  });

  test('shows uploaded file name and analyze button after file selection', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });
    await page.goto('/');
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });

    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'my-resume.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 test content'),
    });

    await expect(page.getByText('my-resume.pdf')).toBeVisible();
    await expect(page.getByRole('button', { name: /開始分析/i })).toBeVisible();
  });
});
