const { test, expect } = require('@playwright/test');

test.describe('Resume Scanner Critical Path (Desktop)', () => {

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
    await page.goto('/');
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });
  });

  test('user can upload PDF and view 5 result cards @smoke', async ({ page }) => {
    await test.step('upload PDF file', async () => {
      const fileChooserPromise = page.waitForEvent('filechooser');
      await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles({
        name: 'my-resume.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from('%PDF-1.4 test content'),
      });
      await expect(page.getByText('my-resume.pdf')).toBeVisible();
    });

    await test.step('click analyze button', async () => {
      await page.getByRole('button', { name: /開始分析/i }).click();
    });

    await test.step('verify all 5 result cards appear via SSE streaming', async () => {
      // Use mock data content that appears in cards
      await expect(page.getByText('經歷與目標職位方向一致')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('技能廣度足夠，但深度有待加強')).toBeVisible();
      await expect(page.getByText('排版清晰易讀')).toBeVisible();
      await expect(page.getByText('關鍵字覆蓋率中等')).toBeVisible();
      await expect(page.getByText('個人摘要具有清晰的品牌定位')).toBeVisible();
    });

    await test.step('verify first card has complete analysis data', async () => {
      const firstCard = page.locator('.dim-card').first();
      await expect(firstCard).toBeVisible();
      await expect(firstCard.locator('.dim-stars')).toBeVisible();
      await expect(firstCard.locator('.dim-conclusion')).toBeVisible();
      await expect(firstCard.locator('.dim-suggestions')).toBeVisible();
      await expect(firstCard.locator('.dim-quote')).toBeVisible();
      await expect(firstCard.locator('.dim-optimized')).toBeVisible();
      await expect(firstCard.locator('.dim-logic')).toBeVisible();
    });

    await test.step('verify sidebar shows history entry', async () => {
      await expect(page.locator('.sidebar-history .history-item')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('.sidebar-history .history-item-name')).toContainText('my-resume.pdf');
    });
  });

  test('upload new button returns to upload state @smoke', async ({ page }) => {
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'my-resume.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 test content'),
    });
    await page.getByRole('button', { name: /開始分析/i }).click();
    await expect(page.getByText('經歷與目標職位方向一致')).toBeVisible({ timeout: 15000 });

    await test.step('click upload new resume button', async () => {
      await page.locator('.upload-new-btn').dispatchEvent('click');
      await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible();
    });
  });
});
