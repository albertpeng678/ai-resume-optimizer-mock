const { test, expect } = require('@playwright/test');

test.describe('Mobile History Click (Regression)', () => {
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
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });
  });

  test('upload → click history item → back → click same item (mobile)', async ({ page }) => {
    // Step 1: Upload a PDF and analyze it
    await test.step('upload and analyze PDF', async () => {
      const fileChooserPromise = page.waitForEvent('filechooser');
      await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles({
        name: 'my-resume.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from('%PDF-1.4 test content'),
      });
      await expect(page.getByText('my-resume.pdf')).toBeVisible();
      await page.getByRole('button', { name: /開始分析/i }).click();
      // Wait for all 5 cards to appear (SSE streaming)
      await expect(page.getByText('經歷與目標職位方向一致')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('技能廣度足夠，但深度有待加強')).toBeVisible();
      await expect(page.getByText('排版清晰易讀')).toBeVisible();
      await expect(page.getByText('關鍵字覆蓋率中等')).toBeVisible();
      await expect(page.getByText('個人摘要具有清晰的品牌定位')).toBeVisible();
    });

    // Step 2: Verify resultsContainer has children (simulates the state that caused the bug)
    const rcChildren = await page.evaluate(() =>
      document.getElementById('resultsContainer')?.children.length || 0
    );
    expect(rcChildren).toBeGreaterThanOrEqual(5);
    console.log(`resultsContainer children after stream: ${rcChildren}`);

    // Step 3: Switch to history tab (mobile bottom nav)
    await test.step('go to history tab and click first item', async () => {
      await page.locator('#bottomHistory').click();
      await page.waitForTimeout(300);

      // Desktop results should be hidden
      await expect(page.locator('#resultsSection')).toBeHidden();

      // History items should appear
      const historyItems = page.locator('#mobileHistoryList .history-item');
      await expect(historyItems.first()).toBeVisible({ timeout: 5000 });

      // Click the first history item
      await historyItems.first().click();
      await page.waitForTimeout(500);

      // Verify mobile detail shows analysis content
      const detail = page.locator('#mobileDetail');
      await expect(detail).toBeVisible();
      const dimCards = await page.evaluate(() =>
        document.querySelectorAll('#mobileDetail .dim-card').length
      );
      console.log(`dim cards after 1st click: ${dimCards}`);
      expect(dimCards).toBeGreaterThanOrEqual(1);
    });

    // Step 4: Click back, then click the SAME history item again
    await test.step('click back → click SAME item → verify detail', async () => {
      // Click back
      const backBtn = page.locator('.mobile-back');
      await backBtn.click();
      await page.waitForTimeout(300);

      // Verify detail is hidden
      await expect(page.locator('#mobileDetail')).toBeHidden();

      // Click the SAME history item again
      const historyItems = page.locator('#mobileHistoryList .history-item');
      await expect(historyItems.first()).toBeVisible();
      await historyItems.first().click();
      await page.waitForTimeout(500);

      // VERIFY: detail should show again (this was the bug)
      const detail = page.locator('#mobileDetail');
      await expect(detail).toBeVisible();
      const dimCards = await page.evaluate(() =>
        document.querySelectorAll('#mobileDetail .dim-card').length
      );
      console.log(`dim cards after 2nd click (same item): ${dimCards}`);
      expect(dimCards).toBeGreaterThanOrEqual(1);
    });
  });
});
