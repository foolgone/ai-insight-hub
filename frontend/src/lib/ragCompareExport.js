import { caseDiffMeta, isSameConfigComparison, metricShort, shortId } from './ragEvaluation'

/** 对比导出 schema 版本（P1-3a）。 */
export const COMPARE_EXPORT_SCHEMA_VERSION = 'm3.compare.export.v1'

/** Judge beta 噪声提示：导出文件必须携带，避免把 delta 当优化效果。 */
export const COMPARE_EXPORT_NOISE_NOTICE =
  'Judge 为 beta；同配置/同输入的两条 Run 也可能出现 ±0.2 波动。' +
  'delta 不代表因果变化，不能直接当作优化效果；建议重复 3 次或确认 RAG 输入/配置确实不同后再判断。'

const CASE_METRICS = ['faithfulness', 'answer_correctness', 'answer_relevancy']

function runExportMeta(run) {
  const judgeConfig = run?.judge_config || run?.config_snapshot?.judge_config || {}
  const retrieval = run?.retrieval_config || {}
  return {
    run_id: run?.id ?? null,
    dataset_id: run?.dataset_id ?? null,
    dataset_name: run?.dataset_name ?? null,
    dataset_version_id: run?.dataset_version_id ?? null,
    status: run?.status ?? null,
    execution_mode: run?.execution_mode ?? null,
    adapter: run?.adapter ?? null,
    top_k: retrieval.top_k ?? run?.config_snapshot?.top_k ?? null,
    judge_model: judgeConfig.model ?? run?.config_snapshot?.model ?? null,
    prompt_version: judgeConfig.prompt_version ?? null,
    completed_at: run?.completed_at ?? null,
  }
}

function caseMetric(diff, metricName) {
  const row = (diff?.deltas || []).find(item => item.name === metricName)
  return {
    base: typeof row?.base === 'number' ? row.base : null,
    target: typeof row?.target === 'number' ? row.target : null,
    delta: typeof row?.delta === 'number' ? row.delta : null,
  }
}

function exportCase(row) {
  const metrics = {}
  for (const name of CASE_METRICS) {
    const values = caseMetric(row.diff, name)
    metrics[name] = values
  }
  const status = row.diff?.status ?? 'unprocessed'
  return {
    dataset_item_id: row.itemId,
    item_key: row.item?.item_key ?? null,
    question: row.item?.query ?? null,
    base_faithfulness: metrics.faithfulness.base,
    target_faithfulness: metrics.faithfulness.target,
    delta_faithfulness: metrics.faithfulness.delta,
    base_answer_correctness: metrics.answer_correctness.base,
    target_answer_correctness: metrics.answer_correctness.target,
    delta_answer_correctness: metrics.answer_correctness.delta,
    base_answer_relevancy: metrics.answer_relevancy.base,
    target_answer_relevancy: metrics.answer_relevancy.target,
    delta_answer_relevancy: metrics.answer_relevancy.delta,
    verdict: status,
    verdict_label: caseDiffMeta(status).label,
    driver_metric: row.diff?.driver?.name ?? null,
    driver_delta: row.diff?.driver?.delta ?? null,
    note: row.diff?.note ?? null,
  }
}

function compareFlags(base, target) {
  const left = runExportMeta(base)
  const right = runExportMeta(target)
  const sameDataset = Boolean(left.dataset_id && left.dataset_id === right.dataset_id)
  const sameVersion = Boolean(
    left.dataset_version_id && left.dataset_version_id === right.dataset_version_id
  )
  const sameAdapter = Boolean(left.adapter && left.adapter === right.adapter)
  const sameMode = Boolean(left.execution_mode && left.execution_mode === right.execution_mode)
  const sameTopK = left.top_k === null || right.top_k === null ? null : left.top_k === right.top_k
  return {
    same_dataset: sameDataset,
    same_version: sameVersion,
    same_adapter: sameAdapter,
    same_mode: sameMode,
    same_top_k: sameTopK,
    same_config: isSameConfigComparison(base, target),
    judge_beta: true,
    noise_notice: COMPARE_EXPORT_NOISE_NOTICE,
  }
}

/**
 * 生成对比导出对象（CSV/JSON 共用）。只导出页面上实际对比的 Case（默认最多 200）。
 * @param {{
 *   base: object|null,
 *   target: object|null,
 *   metricRows: Array<object>,
 *   rows: Array<object>,
 *   diffCounts: object,
 *   alignedCount?: number,
 *   caseTruncated?: boolean,
 *   exportedAt?: Date|string,
 *   maxCases?: number,
 * }} params
 */
export function buildCompareExportPayload({
  base,
  target,
  metricRows = [],
  rows = [],
  diffCounts = {},
  alignedCount = rows.length,
  caseTruncated = false,
  exportedAt = new Date(),
  maxCases = 200,
}) {
  const exportedAtIso = typeof exportedAt === 'string' ? exportedAt : exportedAt.toISOString()
  const cases = rows.slice(0, maxCases).map(exportCase)
  const truncated = Boolean(caseTruncated) || rows.length > cases.length
  const counts = {
    improved: diffCounts.improved ?? 0,
    regressed: diffCounts.regressed ?? 0,
    unchanged: diffCounts.unchanged ?? 0,
    invalid: diffCounts.invalid ?? 0,
    unprocessed: diffCounts.unprocessed ?? 0,
  }
  return {
    schema_version: COMPARE_EXPORT_SCHEMA_VERSION,
    exported_at: exportedAtIso,
    base: runExportMeta(base),
    target: runExportMeta(target),
    comparison: compareFlags(base, target),
    metrics: metricRows.map(row => ({
      metric_name: row.name,
      metric_short: row.short ?? metricShort(row.name),
      label: row.label ?? null,
      base: row.base ?? null,
      target: row.target ?? null,
      delta: row.delta ?? null,
    })),
    case_summary: {
      ...counts,
      total: Object.values(counts).reduce((sum, value) => sum + value, 0),
      aligned_total: alignedCount,
      exported_cases: cases.length,
      case_truncated: truncated,
      truncation_note: truncated
        ? `仅导出前 ${maxCases} 个 Case（对齐后共 ${alignedCount} 个）。`
        : null,
    },
    cases,
  }
}

/** CSV 单元格转义：逗号、引号、换行；中文原样保留。 */
export function csvEscape(value) {
  if (value === null || value === undefined) return ''
  const text = String(value)
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

/** CSV 单元格：转义 + Excel 公式注入防护（仅字符串）。 */
export function csvCell(value) {
  if (value === null || value === undefined) return ''
  let text = String(value)
  if (typeof value === 'string' && /^[=+\-@]/.test(text)) {
    text = `'${text}`
  }
  return csvEscape(text)
}

/** 单行 CSV（数组 → 逗号分隔）。 */
export function csvRow(values) {
  return values.map(csvCell).join(',')
}

const CASE_COLUMNS = [
  ['dataset_item_id', item => item.dataset_item_id],
  ['item_key', item => item.item_key],
  ['question', item => item.question],
  ['base_faithfulness', item => item.base_faithfulness],
  ['target_faithfulness', item => item.target_faithfulness],
  ['delta_faithfulness', item => item.delta_faithfulness],
  ['base_answer_correctness', item => item.base_answer_correctness],
  ['target_answer_correctness', item => item.target_answer_correctness],
  ['delta_answer_correctness', item => item.delta_answer_correctness],
  ['base_answer_relevancy', item => item.base_answer_relevancy],
  ['target_answer_relevancy', item => item.target_answer_relevancy],
  ['delta_answer_relevancy', item => item.delta_answer_relevancy],
  ['verdict', item => item.verdict],
  ['verdict_label', item => item.verdict_label],
  ['driver_metric', item => item.driver_metric],
  ['driver_delta', item => item.driver_delta],
  ['note', item => item.note],
]

/**
 * 生成 CSV 文本（含 UTF-8 BOM）。
 * 顶部为 `# key=value` 元数据块，空行后是 Case 明细表；Excel 可直接打开。
 * @param {ReturnType<typeof buildCompareExportPayload>} payload
 */
export function toCompareCsv(payload) {
  const summary = payload.case_summary
  const meta = [
    ['schema_version', payload.schema_version],
    ['exported_at', payload.exported_at],
    ['base_run_id', payload.base.run_id],
    ['target_run_id', payload.target.run_id],
    ['base_dataset', payload.base.dataset_name],
    ['target_dataset', payload.target.dataset_name],
    ['base_dataset_version_id', payload.base.dataset_version_id],
    ['target_dataset_version_id', payload.target.dataset_version_id],
    ['base_execution_mode', payload.base.execution_mode],
    ['target_execution_mode', payload.target.execution_mode],
    ['base_adapter', payload.base.adapter],
    ['target_adapter', payload.target.adapter],
    ['base_top_k', payload.base.top_k],
    ['target_top_k', payload.target.top_k],
    ['base_judge_model', payload.base.judge_model],
    ['target_judge_model', payload.target.judge_model],
    ['base_prompt_version', payload.base.prompt_version],
    ['target_prompt_version', payload.target.prompt_version],
    ['same_config', payload.comparison.same_config],
    ['case_improved', summary.improved],
    ['case_regressed', summary.regressed],
    ['case_unchanged', summary.unchanged],
    ['case_invalid', summary.invalid],
    ['case_unprocessed', summary.unprocessed],
    ['exported_cases', summary.exported_cases],
    ['aligned_total', summary.aligned_total],
    ['case_truncated', summary.case_truncated],
    ['truncation_note', summary.truncation_note],
    ['noise_notice', payload.comparison.noise_notice],
  ]
  const lines = [
    '\ufeff# RAG Run Compare Export',
    ...meta.map(([key, value]) => `# ${key}=${csvCell(value)}`),
    '',
    csvRow(CASE_COLUMNS.map(([name]) => name)),
  ]
  for (const item of payload.cases) {
    lines.push(csvRow(CASE_COLUMNS.map(([, getter]) => getter(item))))
  }
  return `${lines.join('\r\n')}\r\n`
}

/** 导出文件名：rag-compare_<base8>_<target8>_<timestamp>.csv/json。 */
export function buildCompareExportFilename(format, baseId, targetId, exportedAt = new Date()) {
  const iso = typeof exportedAt === 'string' ? exportedAt : exportedAt.toISOString()
  const stamp = iso.replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')
  return `rag-compare_${shortId(baseId)}_${shortId(targetId)}_${stamp}.${format}`
}

/** 触发浏览器下载（仅当前用户会话内，不写公开桶）。 */
export function downloadTextFile(filename, text, mimeType) {
  const blob = new Blob([text], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  // 等下载启动后再释放，避免部分浏览器取消 Blob 下载。
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
