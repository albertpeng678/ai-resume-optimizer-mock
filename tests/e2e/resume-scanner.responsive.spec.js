const { test, expect } = require('@playwright/test');

test.describe('Responsive Layout', () => {
  test.beforeEach(async ({ page, request }) => {
    await request.post('/__reset');
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
  });

  test('Desktop: sidebar is permanently visible', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');
    await expect(page.locator('.sidebar')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.sidebar')).not.toHaveClass(/open/);
    await expect(page.locator('.hamburger')).toBeHidden();
  });

  test('Tablet: sidebar hidden by default, toggled via hamburger', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await expect(page.locator('.sidebar')).not.toHaveClass(/open/);

    await page.locator('.hamburger').click();
    await expect(page.locator('.sidebar')).toHaveClass(/open/);
    await expect(page.locator('.sidebar-backdrop')).toHaveClass(/open/);

    await page.locator('.sidebar-backdrop').click();
    await expect(page.locator('.sidebar')).not.toHaveClass(/open/);
  });

  test('Mobile: bottom nav visible', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await expect(page.locator('.bottom-nav')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.bottom-nav')).toContainText('分析');
    await expect(page.locator('.bottom-nav')).toContainText('歷史記錄');
  });

  test('Mobile: switching between upload and history tabs', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });

    await page.locator('#bottomHistory').click();
    await expect(page.locator('#mobileHistoryList').getByText(/尚無分析記錄/i)).toBeVisible();

    await page.locator('#bottomUpload').click();
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible();
  });
});
