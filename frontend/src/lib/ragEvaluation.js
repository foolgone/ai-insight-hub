/** RAG 评测工作台的数据映射与展示辅助（纯函数，便于单测）。 */

export const RUN_STATUS_META = {
  pending: { label: '排队中', variant: 'warning' },
  queued: { label: '排队中', variant: 'warning' },
  running: { label: '运行中', variant: 'info' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '失败', variant: 'error' },
  cancelled: { label: '已取消', variant: 'default' },
}

export const RESULT_STATUS_META = {
  evaluated: { label: '已评分', variant: 'success' },
  invalid: { label: 'invalid', variant: 'warning' },
  failed: { label: '失败', variant: 'error' },
  skipped: { label: '跳过', variant: 'default' },
}

export const METRIC_LABELS = {
  faithfulness: 'Faithfulness',
  answer_correctness: 'Answer Correctness',
  answer_relevancy: 'Answer Relevancy',
  hit_rate: 'Hit Rate',
  mrr: 'MRR',
  context_recall: 'Context Recall',
  context_precision_at_k: 'Context Precision@K',
  context_precision_ap_at_k: 'Context Precision (AP)',
}

export const METRIC_SHORT = {
  faithfulness: 'F',
  answer_correctness: 'C',
  answer_relevancy: 'R',
}

export const JUDGE_METRICS = ['faithfulness', 'answer_correctness', 'answer_relevancy']

export function runStatusMeta(status) {
  return RUN_STATUS_META[status] || { label: status || '未知', variant: 'default' }
}

export function resultStatusMeta(status) {
  return RESULT_STATUS_META[status] || { label: status || '未知', variant: 'default' }
}

export function metricLabel(name) {
  return METRIC_LABELS[name] || name
}

export function metricShort(name) {
  return METRIC_SHORT[name] || name
}

/** 聚合里的指标均值；缺失返回 null（页面显示 —，不伪装成 0）。 */
export function metricMean(aggregate, metricName) {
  const value = aggregate?.metrics?.[metricName]?.mean
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** 指标汇总行（F/C/R 顺序固定；缺失指标也返回，值为 null）。 */
export function judgeMetricRows(aggregate) {
  return JUDGE_METRICS.map(name => ({
    name,
    label: metricLabel(name),
    short: metricShort(name),
    mean: metricMean(aggregate, name),
    evaluated: aggregate?.metrics?.[name]?.evaluated ?? 0,
    invalid: aggregate?.metrics?.[name]?.invalid ?? 0,
    failed: aggregate?.metrics?.[name]?.failed ?? 0,
    skipped: aggregate?.metrics?.[name]?.skipped ?? 0,
    coverage: aggregate?.metrics?.[name]?.coverage ?? 0,
    skipReasons: aggregate?.metrics?.[name]?.skip_reasons || {},
  }))
}

export function formatScore(value, digits = 3) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toFixed(digits)
}

export function formatPercent(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return `${Math.round(value * 100)}%`
}

export function shortId(value, length = 8) {
  if (!value) return '—'
  return String(value).slice(0, length)
}

export function itemDisplayLabel(item) {
  if (!item) return '—'
  if (item.item_key) return item.item_key
  if (item.query) return item.query
  return shortId(item.id)
}

/** 把逐指标结果按 dataset_item_id 聚合成 case 行。 */
export function groupResultsByItem(results = []) {
  const map = new Map()
  for (const row of results) {
    const key = row?.dataset_item_id || row?.id
    if (!key) continue
    if (!map.has(key)) {
      map.set(key, {
        itemId: key,
        metrics: {},
        traceId: null,
        invalidCount: 0,
        failedCount: 0,
        skippedCount: 0,
      })
    }
    const entry = map.get(key)
    if (row.metric_name) entry.metrics[row.metric_name] = row
    if (row.trace_id) entry.traceId = row.trace_id
    if (row.status === 'invalid') entry.invalidCount += 1
    if (row.status === 'failed') entry.failedCount += 1
    if (row.status === 'skipped') entry.skippedCount += 1
  }
  return Array.from(map.values()).sort((left, right) =>
    String(left.itemId).localeCompare(String(right.itemId))
  )
}

export function caseKnownIssue(caseRow) {
  if (!caseRow) return null
  const invalid = Object.values(caseRow.metrics || {}).find(row => row.status === 'invalid')
  if (invalid) {
    return invalid.invalid_reason || 'contract_violation'
  }
  const failed = Object.values(caseRow.metrics || {}).find(row => row.status === 'failed')
  if (failed) {
    return failed.error_message || 'execution_failed'
  }
  return null
}

export function invalidReasonLabel(reason) {
  if (!reason) return '—'
  const mapping = {
    contract_violation: '输出契约不合法（已标 invalid，不计入均值）',
    no_scorable_claims: '没有可评分 claim（跳过）',
    no_claims: '没有 claims（跳过）',
  }
  return mapping[reason] || reason
}

/** Run 级别的 known issues（用于 Beta 面板与详情页提示）。 */
export function runKnownIssues(run) {
  if (!run) return []
  const issues = []
  if (run.invalid_items > 0) {
    issues.push({
      key: 'invalid',
      label: 'invalid 结果',
      count: run.invalid_items,
      hint: 'Judge 输出未通过契约校验，已标 invalid；不参与均值，人工复核可覆盖。',
    })
  }
  if (run.failed_items > 0) {
    issues.push({
      key: 'failed',
      label: '执行失败',
      count: run.failed_items,
      hint: '调用或解析失败；可在原 Run 上重试失败样本（P0 暂未提供按钮）。',
    })
  }
  if (run.skipped_items > 0) {
    issues.push({
      key: 'skipped',
      label: '跳过',
      count: run.skipped_items,
      hint: '缺少可评分内容（如 no_scorable_claims），不参与均值。',
    })
  }
  if (run.unprocessed_items > 0) {
    issues.push({
      key: 'unprocessed',
      label: '未处理',
      count: run.unprocessed_items,
      hint: '任务中断或超出 limit；未产生结果。',
    })
  }
  return issues
}

/** 从 Faithfulness 结果 details 中取 claims（兼容 details.claims 与 agent_contract）。 */
export function claimsOf(result) {
  const details = result?.details || {}
  const claims = details.claims
  if (Array.isArray(claims)) return claims
  const nested = details.agent_contract?.claims
  return Array.isArray(nested) ? nested : []
}

/** 从 claim 的 evidence_refs 中取 quote 文本。 */
export function quotesOf(claim) {
  const refs = Array.isArray(claim?.evidence_refs) ? claim.evidence_refs : []
  return refs
    .map(ref => (typeof ref === 'string' ? ref : ref?.quote))
    .filter(value => typeof value === 'string' && value.trim())
}

export function claimSupportMeta(status) {
  if (status === 'supported') return { label: 'supported', variant: 'success' }
  if (status === 'unsupported') return { label: 'unsupported', variant: 'error' }
  if (status === 'insufficient_evidence') {
    return { label: 'insufficient', variant: 'warning' }
  }
  return { label: status || '—', variant: 'default' }
}

export const CASE_DIFF_META = {
  improved: { label: '变好', variant: 'success' },
  regressed: { label: '变差', variant: 'error' },
  unchanged: { label: '不变', variant: 'default' },
  invalid: { label: 'invalid', variant: 'warning' },
  unprocessed: { label: '未处理', variant: 'default' },
}

export function caseDiffMeta(status) {
  return CASE_DIFF_META[status] || { label: status || '未知', variant: 'default' }
}

/** Case 级分数：按 F → C → R 取首个有效分数（用于展示/兼容）。 */
export function caseScore(caseRow) {
  for (const metric of JUDGE_METRICS) {
    const value = caseRow?.metrics?.[metric]?.score
    if (typeof value === 'number' && Number.isFinite(value)) return value
  }
  return null
}

/** 逐指标 base/target/delta（缺失侧为 null）。 */
export function caseMetricDeltas(baseCase, targetCase) {
  return JUDGE_METRICS.map(name => {
    const base = baseCase?.metrics?.[name]?.score
    const target = targetCase?.metrics?.[name]?.score
    return {
      name,
      short: metricShort(name),
      base: typeof base === 'number' ? base : null,
      target: typeof target === 'number' ? target : null,
      delta:
        typeof base === 'number' && typeof target === 'number'
          ? Number((target - base).toFixed(6))
          : null,
    }
  })
}

function meanScore(caseRow) {
  const values = JUDGE_METRICS.map(name => caseRow?.metrics?.[name]?.score).filter(
    value => typeof value === 'number' && Number.isFinite(value)
  )
  if (!values.length) return null
  return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(6))
}

/**
 * 两 Run 的 Case diff：
 * - target 无结果 → unprocessed
 * - target 任一指标 invalid → invalid
 * - target 无有效分数 → unprocessed
 * - 按 F/C/R 中绝对变化最大的指标判定 improved/regressed/unchanged
 * - base 无有效分数但 target 有 → improved（备注）
 */
export function classifyCaseDiff(baseCase, targetCase, epsilon = 1e-6) {
  const baseScore = caseScore(baseCase)
  const targetMetrics = Object.values(targetCase?.metrics || {})
  if (!targetCase || targetMetrics.length === 0) {
    return {
      status: 'unprocessed',
      baseScore,
      targetScore: null,
      delta: null,
      deltas: caseMetricDeltas(baseCase, targetCase),
      driver: null,
      note: 'target 无结果',
    }
  }
  if (targetMetrics.some(metric => metric.status === 'invalid')) {
    return {
      status: 'invalid',
      baseScore,
      targetScore: caseScore(targetCase),
      delta: null,
      deltas: caseMetricDeltas(baseCase, targetCase),
      driver: null,
      note: 'target 有 invalid 指标',
    }
  }
  const targetScore = caseScore(targetCase)
  if (typeof targetScore !== 'number') {
    return {
      status: 'unprocessed',
      baseScore,
      targetScore: null,
      delta: null,
      deltas: caseMetricDeltas(baseCase, targetCase),
      driver: null,
      note: 'target 无有效分数',
    }
  }

  const deltas = caseMetricDeltas(baseCase, targetCase)
  const comparable = deltas.filter(row => row.delta !== null)
  const baseMean = meanScore(baseCase)
  const targetMean = meanScore(targetCase)
  const meanDelta =
    baseMean !== null && targetMean !== null ? Number((targetMean - baseMean).toFixed(6)) : null

  if (!comparable.length) {
    return {
      status: 'improved',
      baseScore,
      targetScore,
      delta: meanDelta,
      deltas,
      driver: null,
      note: 'base 无同指标分数',
    }
  }

  const driver = comparable.reduce((max, row) =>
    Math.abs(row.delta) > Math.abs(max.delta) ? row : max
  )
  if (Math.abs(driver.delta) <= epsilon) {
    return {
      status: 'unchanged',
      baseScore,
      targetScore,
      delta: 0,
      deltas,
      driver,
      note: '',
    }
  }
  const sign = driver.delta > 0 ? '+' : ''
  return {
    status: driver.delta > 0 ? 'improved' : 'regressed',
    baseScore,
    targetScore,
    delta: meanDelta,
    deltas,
    driver,
    note: `${driver.short} ${sign}${driver.delta.toFixed(3)}`,
  }
}

/** 指标 base/target/delta；任一侧缺失时 delta=null。 */
export function metricComparisonRows(baseAggregate, targetAggregate) {
  return JUDGE_METRICS.map(name => {
    const base = metricMean(baseAggregate, name)
    const target = metricMean(targetAggregate, name)
    return {
      name,
      label: metricLabel(name),
      short: metricShort(name),
      base,
      target,
      delta:
        typeof base === 'number' && typeof target === 'number'
          ? Number((target - base).toFixed(6))
          : null,
    }
  })
}

/** Case diff 计数（按分类）。 */
export function countCaseDiff(rows = []) {
  const counts = { improved: 0, regressed: 0, unchanged: 0, invalid: 0, unprocessed: 0 }
  for (const row of rows) {
    if (counts[row.diff.status] !== undefined) counts[row.diff.status] += 1
  }
  return counts
}
