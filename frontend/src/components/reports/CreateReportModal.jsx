import { useEffect, useState } from 'react'
import { format as formatDate } from 'date-fns'
import { Button } from '../Button'
import { DatePicker } from '../DatePicker'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { RadioGroup } from '../Radio'
import { Select } from '../Select'
import { Switch } from '../Switch'
import { useCreateReport } from '../../hooks/useReports'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const REPORT_TYPES = [
  { label: '质量分析报告', value: 'quality' },
  { label: '知识库报告', value: 'knowledge' },
  { label: '洞察报告', value: 'insight' },
  { label: '综合分析报告', value: 'comprehensive' },
]

const FORMATS = [
  { label: 'Markdown', value: 'markdown' },
  { label: 'Excel', value: 'excel' },
  { label: 'PDF', value: 'pdf' },
]

/**
 * 生成报告（F-407）：4 类报告、markdown/excel/pdf 三种格式（T8），202 入队。
 * @param {{ open: boolean, onClose: () => void, datasourceId: string|null }} props
 */
export function CreateReportModal({ open, onClose, datasourceId }) {
  const mutation = useCreateReport()
  const [reportType, setReportType] = useState('quality')
  const [format, setFormat] = useState('markdown')
  const [title, setTitle] = useState('')
  const [dateRange, setDateRange] = useState({ start: '', end: '' })
  const [includeCharts, setIncludeCharts] = useState(true)
  const [includeRecommendations, setIncludeRecommendations] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setReportType('quality')
    setFormat('markdown')
    setTitle(`质量分析报告-${formatDate(new Date(), 'yyyyMMdd')}`)
    setDateRange({ start: '', end: '' })
    setIncludeCharts(true)
    setIncludeRecommendations(true)
    setError('')
  }, [open])

  const handleSubmit = async () => {
    if (!datasourceId) {
      setError('请先选择数据源')
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
          report_type: reportType,
          format,
          config: {
            include_charts: includeCharts,
            include_recommendations: includeRecommendations,
            ...(dateRange.start && dateRange.end
              ? { time_range: { start: dateRange.start, end: dateRange.end } }
              : {}),
          },
        },
      })
      notify.success('报告生成任务已入队')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="生成报告"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={mutation.isPending} disabled={mutation.isPending}>
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

        <div>
          <span className="mb-1 block text-sm font-medium text-gray-700">报告类型</span>
          <Select
            options={REPORT_TYPES}
            value={reportType}
            onChange={value => {
              setReportType(value)
              const label = REPORT_TYPES.find(item => item.value === value)?.label || '报告'
              setTitle(`${label}-${formatDate(new Date(), 'yyyyMMdd')}`)
            }}
            disabled={mutation.isPending}
          />
        </div>

        <div>
          <label htmlFor="report-title" className="mb-1 block text-sm font-medium text-gray-700">
            标题
          </label>
          <Input
            id="report-title"
            value={title}
            onChange={setTitle}
            disabled={mutation.isPending}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <span className="mb-1 block text-sm font-medium text-gray-700">时间范围（可选）</span>
            <DatePicker value={dateRange} onChange={setDateRange} disabled={mutation.isPending} />
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
        </div>

        <div className="space-y-3 rounded border border-gray-200 p-3">
          <Switch
            label="包含图表"
            checked={includeCharts}
            onCheckedChange={setIncludeCharts}
            disabled={mutation.isPending}
          />
          <Switch
            label="包含建议"
            checked={includeRecommendations}
            onCheckedChange={setIncludeRecommendations}
            disabled={mutation.isPending}
          />
          <p className="text-xs text-gray-500">
            支持 markdown / excel / pdf；html 后端返回 422，界面不提供。
          </p>
        </div>
      </div>
    </Modal>
  )
}
