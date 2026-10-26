import { expect, test } from '@playwright/test'
import { CREDENTIALS, loginViaUi } from './fixtures'

test.describe('认证与守卫', () => {
  test('未登录访问受保护路由 → 跳转登录页并保留 returnUrl', async ({ page }) => {
    await page.goto('/reports')

    await expect(page).toHaveURL(/\/login\?returnUrl=%2Freports/)
    await expect(page.getByRole('heading', { name: '欢迎使用 AI Insight Hub' })).toBeVisible()
  })

  test('登录成功进入 Dashboard；登出后受保护路由不可达', async ({ page }) => {
    await loginViaUi(page)
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()

    await page.getByRole('button', { name: '打开用户菜单' }).click()
    await page.getByRole('menuitem', { name: '退出登录' }).click()

    await expect(page).toHaveURL(/\/login/)
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
  })

  test('错误密码 → 提示错误且停留在登录页', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('邮箱').fill(CREDENTIALS.email)
    await page.getByLabel('密码').fill('definitely-wrong-password')
    await page.getByRole('button', { name: '登录', exact: true }).click()

    await expect(page.getByRole('alert')).toContainText('邮箱或密码错误')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: '欢迎使用 AI Insight Hub' })).toBeVisible()
  })
})
