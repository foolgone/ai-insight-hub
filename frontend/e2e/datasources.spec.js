import { expect, test } from '@playwright/test'
import { createDatasource, deleteDatasource, loginViaUi, uniqueName } from './fixtures'

test.describe('数据源', () => {
  test('新数据源出现在列表，可通过操作菜单物理删除', async ({ page }) => {
    const name = uniqueName('e2e-ds')
    const datasourceId = await createDatasource(name)
    try {
      await loginViaUi(page)
      await page.goto('/data-sources')

      // 名称会同时出现在顶部数据源选择器，断言限定在卡片标题
      await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()

      await page.getByRole('button', { name: `数据源操作：${name}` }).click()
      await page.getByRole('menuitem', { name: '删除数据源' }).click()

      const dialog = page.getByRole('dialog', { name: '删除数据源' })
      await expect(dialog).toBeVisible()
      await dialog.getByRole('checkbox').click()
      await dialog.getByRole('button', { name: '确认删除' }).click()

      await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0)
    } finally {
      await deleteDatasource(datasourceId)
    }
  })
})
