import { expect, test } from '@playwright/test'

test('未知路由 → 404 页面（含返回 Dashboard 入口）', async ({ page }) => {
  await page.goto('/this-route-does-not-exist')

  await expect(page.getByRole('heading', { name: '页面不存在' })).toBeVisible()
  await expect(page.getByRole('link', { name: '返回 Dashboard' })).toBeVisible()
})
