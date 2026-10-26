import { expect, test } from '@playwright/test'
import {
  createDatasource,
  deleteDatasource,
  loginViaUi,
  selectDatasource,
  uniqueName,
} from './fixtures'

test.describe('知识库（手动 CRUD，不触发 LLM）', () => {
  test('新建 FAQ → 列表可见 → 删除', async ({ page }) => {
    const datasourceName = uniqueName('e2e-kb-ds')
    const question = uniqueName('E2E 退款问题')
    const datasourceId = await createDatasource(datasourceName)
    try {
      await loginViaUi(page)
      await page.goto('/knowledge-base')
      await selectDatasource(page, datasourceName)

      await page.getByRole('button', { name: '新建条目' }).click()
      const drawer = page.getByRole('dialog', { name: '新建知识条目' })
      await expect(drawer).toBeVisible()
      await drawer.getByLabel(/^问题/).fill(question)
      await drawer.getByLabel(/^答案/).fill('7 天内可申请，审核通过后原路退回。')
      await drawer.getByRole('button', { name: '保存' }).click()

      // 后端会同步计算 embedding（首次加载模型可能数十秒），等抽屉关闭再断言列表
      await expect(drawer).toBeHidden({ timeout: 90_000 })
      await expect(page.getByText(question)).toBeVisible({ timeout: 20_000 })

      const card = page.locator('article').filter({ hasText: question })
      await card.getByRole('button', { name: '删除' }).click()
      await page.getByRole('button', { name: '确认', exact: true }).click()

      await expect(page.getByText(question)).toHaveCount(0)
    } finally {
      await deleteDatasource(datasourceId)
    }
  })
})
