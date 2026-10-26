import { expect, test } from '@playwright/test'
import {
  createDatasource,
  deleteDatasource,
  loginViaUi,
  selectDatasource,
  uniqueName,
} from './fixtures'

test.describe('报告中心（仅表单/校验，不提交生成以避开 LLM）', () => {
  test('生成弹窗可选 PDF、必填校验生效、取消关闭', async ({ page }) => {
    const datasourceName = uniqueName('e2e-report-ds')
    const datasourceId = await createDatasource(datasourceName)
    try {
      await loginViaUi(page)
      await page.goto('/reports')
      await selectDatasource(page, datasourceName)

      await page.getByRole('button', { name: '生成报告' }).click()
      const dialog = page.getByRole('dialog', { name: '生成报告' })
      await expect(dialog).toBeVisible()

      // PDF 选项可用且可选中（T8）
      const pdfRadio = dialog.getByRole('radio', { name: 'PDF' })
      await pdfRadio.click()
      await expect(pdfRadio).toBeChecked()

      // 清空标题 → 必填校验
      await dialog.getByLabel('标题').fill('')
      await dialog.getByRole('button', { name: '生成报告' }).click()
      await expect(dialog.getByRole('alert')).toContainText('请输入报告标题')

      await dialog.getByRole('button', { name: '取消' }).click()
      await expect(dialog).toHaveCount(0)
    } finally {
      await deleteDatasource(datasourceId)
    }
  })
})
