import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { format as formatDate } from 'date-fns'
import { Button } from '../Button'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { RadioGroup } from '../Radio'
import { useCreateReport } from '../../hooks/useReports'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const FORMATS = [
  { label: 'Markdown', value: 'markdown' },
  { label: 'Excel', value: 'excel' },
  { label: 'PDF', value: 'pdf' },
]

/**
 * 生成 Run 对比报告（P1-3b）：复用报告中心模板/任务链路，
 * 对比章节由 report_service 确定性渲染，不调用报告 Agent。
 * @param {{ open: boolean, onClose: () => void, datasourceId: string|null, comparison: Object|null }} props
 */
export function ComparisonReportModal({ open, onClose, datasourceId, comparison }) {
  const mutation = useCreateReport()
  const navigate = useNavigate()
  const [format, setFormat] = useState('markdown')
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setFormat('markdown')
    setTitle(`Run 对比报告-${formatDate(new Date(), 'yyyyMMdd')}`)
    setError('')
  }, [open])

  const handleSubmit = async () => {
    if (!datasourceId) {
      setError('请先在顶部选择数据源')
      return
    }
    if (!comparison) {
      setError('当前没有可对比的 Case')
      return
    }
    if (!title.trim()) {
      setError('请输入报告标题')
      return
    }
    try {
      await mutation.mutateAsync({
        datasourceId,
        payload: {
          title: title.trim(),
          report_type: 'comprehensive',
          format,
          config: {
            include_charts: false,
            include_recommendations: false,
            run_comparison: comparison,
          },
        },
      })
      notify.success('Run 对比报告已入队')
      onClose()
      navigate('/reports')
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="生成 Run 对比报告"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={mutation.isPending}>
            生成报告
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? (
          <div
            role="alert"
            className="rounded border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700"
          >
            {error}
          </div>
        ) : null}

        {!datasourceId ? (
          <p role="alert" className="rounded bg-warning-50 p-3 text-sm text-warning-800">
            请先在顶部「数据源选择器」中选择数据源；报告会生成到该数据源下。
          </p>
        ) : (
          <p className="text-xs text-gray-500">
            报告会生成到当前数据源下；对比数字来自当前页面快照，并附带 Judge beta 噪声提示。
          </p>
        )}

        <div>
          <label
            htmlFor="comparison-report-title"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            标题
          </label>
          <Input
            id="comparison-report-title"
            value={title}
            onChange={setTitle}
            disabled={mutation.isPending}
          />
        </div>

        <div>
          <span className="mb-2 block text-sm font-medium text-gray-700">输出格式</span>
          <RadioGroup
            options={FORMATS}
            value={format}
            onChange={setFormat}
            ariaLabel="输出格式"
            disabled={mutation.isPending}
          />
        </div>

        <div className="rounded border border-gray-200 bg-gray-50 p-3 text-xs text-gray-600">
          章节：Base / Target、指标 delta、Case 汇总、Top 变好/变差（最多 5 条）、 beta/noise
          提示、对比页链接。不做显著性检验，不生成优化建议。
        </div>
      </div>
    </Modal>
  )
}
