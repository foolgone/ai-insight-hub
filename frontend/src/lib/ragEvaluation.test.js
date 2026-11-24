import { describe, expect, it } from 'vitest'
import {
  caseKnownIssue,
  claimSupportMeta,
  claimsOf,
  formatPercent,
  formatScore,
  groupResultsByItem,
  invalidReasonLabel,
  itemDisplayLabel,
  judgeMetricRows,
  metricLabel,
  metricMean,
  metricShort,
  quotesOf,
  resultStatusMeta,
  runKnownIssues,
  runStatusMeta,
  shortId,
} from './ragEvaluation'

const AGGREGATE = {
  metrics: {
    faithfulness: {
      mean: 0.75,
      evaluated: 4,
      invalid: 1,
      failed: 0,
      skipped: 1,
      coverage: 0.8,
      skip_reasons: { no_scorable_claims: 1 },
    },
    answer_correctness: { mean: 0.9, evaluated: 5, invalid: 0, failed: 0, skipped: 0 },
    answer_relevancy: { mean: null, evaluated: 0, invalid: 2, failed: 0, skipped: 0 },
  },
}

describe('ragEvaluation helpers', () => {
  it('状态映射与未知回退', () => {
    expect(runStatusMeta('completed')).toEqual({ label: '已完成', variant: 'success' })
    expect(runStatusMeta('unknown').label).toBe('unknown')
    expect(resultStatusMeta('invalid').variant).toBe('warning')
    expect(resultStatusMeta(undefined).label).toBe('未知')
  })

  it('指标标签与均值（null 不伪装为 0）', () => {
    expect(metricLabel('faithfulness')).toBe('Faithfulness')
    expect(metricLabel('custom')).toBe('custom')
    expect(metricShort('answer_correctness')).toBe('C')
    expect(metricMean(AGGREGATE, 'faithfulness')).toBe(0.75)
    expect(metricMean(AGGREGATE, 'answer_relevancy')).toBe(null)
    expect(metricMean(null, 'faithfulness')).toBe(null)
  })

  it('judgeMetricRows 固定 F/C/R 顺序并补齐缺失', () => {
    const rows = judgeMetricRows(AGGREGATE)
    expect(rows.map(row => row.short)).toEqual(['F', 'C', 'R'])
    expect(rows[0].invalid).toBe(1)
    expect(rows[2].mean).toBe(null)
    expect(judgeMetricRows(null)[0].mean).toBe(null)
  })

  it('格式化与 id 截断', () => {
    expect(formatScore(0.12345)).toBe('0.123')
    expect(formatScore(null)).toBe('—')
    expect(formatPercent(0.812)).toBe('81%')
    expect(formatPercent(undefined)).toBe('—')
    expect(shortId('abcdefghijkl')).toBe('abcdefgh')
    expect(shortId(null)).toBe('—')
  })

  it('item 展示标签优先 item_key → query → id', () => {
    expect(itemDisplayLabel({ item_key: 'Q1', query: 'q' })).toBe('Q1')
    expect(itemDisplayLabel({ query: '问题' })).toBe('问题')
    expect(itemDisplayLabel({ id: '123456789' })).toBe('12345678')
    expect(itemDisplayLabel(null)).toBe('—')
  })

  it('按 item 聚合结果并统计 invalid/failed/skipped', () => {
    const cases = groupResultsByItem([
      { dataset_item_id: 'b', metric_name: 'faithfulness', status: 'invalid', trace_id: 't1' },
      { dataset_item_id: 'b', metric_name: 'answer_correctness', status: 'evaluated' },
      { dataset_item_id: 'a', metric_name: 'faithfulness', status: 'failed' },
      { dataset_item_id: 'a', metric_name: 'answer_relevancy', status: 'skipped' },
      { id: 'orphan', metric_name: 'faithfulness', status: 'evaluated' },
      { metric_name: 'faithfulness', status: 'evaluated' },
    ])
    expect(cases.map(item => item.itemId)).toEqual(['a', 'b', 'orphan'])
    expect(cases[1].invalidCount).toBe(1)
    expect(cases[1].traceId).toBe('t1')
    expect(cases[0].failedCount).toBe(1)
    expect(cases[0].skippedCount).toBe(1)
  })

  it('case 已知问题与原因文案', () => {
    const invalid = {
      metrics: { faithfulness: { status: 'invalid', invalid_reason: 'contract_violation' } },
    }
    expect(caseKnownIssue(invalid)).toBe('contract_violation')
    expect(caseKnownIssue({ metrics: {} })).toBe(null)
    expect(invalidReasonLabel('contract_violation')).toContain('契约')
    expect(invalidReasonLabel('custom_reason')).toBe('custom_reason')
    expect(invalidReasonLabel(null)).toBe('—')
  })

  it('runKnownIssues 覆盖四类限制', () => {
    const issues = runKnownIssues({
      invalid_items: 2,
      failed_items: 1,
      skipped_items: 3,
      unprocessed_items: 4,
    })
    expect(issues.map(item => item.key)).toEqual(['invalid', 'failed', 'skipped', 'unprocessed'])
    expect(runKnownIssues({ invalid_items: 0 })).toEqual([])
    expect(runKnownIssues(null)).toEqual([])
  })

  it('claims/quotes 提取与支持状态映射', () => {
    expect(claimsOf({ details: { claims: [{ claim_id: 'cl1' }] } })).toHaveLength(1)
    expect(
      claimsOf({ details: { agent_contract: { claims: [{ claim_id: 'cl2' }] } } })
    ).toHaveLength(1)
    expect(claimsOf(null)).toEqual([])

    expect(
      quotesOf({
        evidence_refs: [{ quote: 'a' }, 'b', { quote: '  ' }, { other: 1 }],
      })
    ).toEqual(['a', 'b'])
    expect(quotesOf(null)).toEqual([])

    expect(claimSupportMeta('supported').variant).toBe('success')
    expect(claimSupportMeta('unsupported').variant).toBe('error')
    expect(claimSupportMeta('insufficient_evidence').label).toBe('insufficient')
    expect(claimSupportMeta(null).label).toBe('—')
  })
})
