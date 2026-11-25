import { describe, expect, it } from 'vitest'
import {
  buildCompareExportFilename,
  buildCompareExportPayload,
  buildComparisonReportPayload,
  COMPARE_EXPORT_NOISE_NOTICE,
  COMPARE_EXPORT_SCHEMA_VERSION,
  csvCell,
  csvEscape,
  toCompareCsv,
  topDiffCases,
} from './ragCompareExport'

const BASE_RUN = {
  id: '5328123c-f3f5-4f6b-9d59-763c5e415719',
  dataset_id: 'ds-1',
  dataset_name: 'M3 P1-2 分页验收数据集',
  dataset_version_id: 'ver-1',
  status: 'completed',
  execution_mode: 'query',
  adapter: 'mock',
  retrieval_config: { top_k: 3 },
  judge_config: { model: 'qwen-flash', prompt_version: 'v1.2.5' },
  completed_at: '2026-11-25T03:33:00Z',
}

const TARGET_RUN = {
  ...BASE_RUN,
  id: '7b2fa311-760b-4064-a45e-648647102250',
  completed_at: '2026-11-25T03:44:00Z',
}

const METRIC_ROWS = [
  {
    name: 'faithfulness',
    label: 'Faithfulness',
    short: 'F',
    base: 0.776,
    target: 0.801,
    delta: 0.026,
  },
  {
    name: 'answer_correctness',
    label: 'Answer Correctness',
    short: 'C',
    base: 0.128,
    target: 0.125,
    delta: -0.003,
  },
  {
    name: 'answer_relevancy',
    label: 'Answer Relevancy',
    short: 'R',
    base: 0.498,
    target: 0.488,
    delta: -0.01,
  },
]

function makeRow(index, status = 'improved') {
  const delta = status === 'regressed' ? -0.2 : status === 'unchanged' ? 0 : 0.2
  const baseScore = 0.5
  const targetScore = status === 'unchanged' ? 0.5 : Number((baseScore + delta).toFixed(1))
  return {
    itemId: `item-${index}`,
    item: {
      item_key: `P12-${String(index).padStart(3, '0')}`,
      query: `问题 ${index}，含逗号、"引号" 与\n换行`,
    },
    baseCase: { metrics: { faithfulness: { score: baseScore } } },
    targetCase: { metrics: { faithfulness: { score: targetScore } } },
    diff: {
      status,
      deltas: [
        { name: 'faithfulness', short: 'F', base: baseScore, target: targetScore, delta },
        { name: 'answer_correctness', short: 'C', base: 0.3, target: 0.3, delta: 0 },
        {
          name: 'answer_relevancy',
          short: 'R',
          base: 0.4,
          target: status === 'regressed' ? 0.2 : 0.4,
          delta: status === 'regressed' ? -0.2 : 0,
        },
      ],
      driver:
        status === 'unchanged'
          ? { name: 'faithfulness', short: 'F', delta: 0 }
          : { name: 'faithfulness', short: 'F', delta },
      note: status === 'unchanged' ? '' : `F ${delta > 0 ? '+' : ''}${delta.toFixed(3)}`,
    },
  }
}

function makeRows(total = 120) {
  return Array.from({ length: total }, (_, index) => {
    if (index < 31) return makeRow(index, 'improved')
    if (index < 63) return makeRow(index, 'regressed')
    return makeRow(index, 'unchanged')
  })
}

const DIFF_COUNTS = { improved: 31, regressed: 32, unchanged: 57, invalid: 0, unprocessed: 0 }

/** 解析 CSV（支持双引号、逗号、换行）。 */
function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    if (inQuotes) {
      if (char === '"' && text[i + 1] === '"') {
        field += '"'
        i += 1
      } else if (char === '"') {
        inQuotes = false
      } else {
        field += char
      }
    } else if (char === '"') {
      inQuotes = true
    } else if (char === ',') {
      row.push(field)
      field = ''
    } else if (char === '\r') {
      // skip
    } else if (char === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else {
      field += char
    }
  }
  if (field !== '' || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows
}

function dataRows(csv) {
  const parsed = parseCsv(csv.replace(/^\ufeff/, ''))
  const headerIndex = parsed.findIndex(row => row[0] === 'dataset_item_id')
  expect(headerIndex).toBeGreaterThan(-1)
  return { header: parsed[headerIndex], rows: parsed.slice(headerIndex + 1) }
}

function payloadFor(overrides = {}) {
  return buildCompareExportPayload({
    base: BASE_RUN,
    target: TARGET_RUN,
    metricRows: METRIC_ROWS,
    rows: makeRows(),
    diffCounts: DIFF_COUNTS,
    alignedCount: 120,
    caseTruncated: false,
    exportedAt: '2026-11-25T04:00:00.000Z',
    ...overrides,
  })
}

describe('csvEscape', () => {
  it('转义逗号、引号、换行，中文原样', () => {
    expect(csvEscape('普通中文')).toBe('普通中文')
    expect(csvEscape('a,b')).toBe('"a,b"')
    expect(csvEscape('a"b')).toBe('"a""b"')
    expect(csvEscape('a\nb')).toBe('"a\nb"')
    expect(csvEscape(null)).toBe('')
  })

  it('公式开头加前缀，避免 Excel 注入', () => {
    expect(csvCell('=SUM(A1)')).toBe("'=SUM(A1)")
    expect(csvCell('正常问题')).toBe('正常问题')
  })
})

describe('buildCompareExportPayload', () => {
  it('包含 schema/元数据/指标/Case，same_config=true', () => {
    const payload = payloadFor()

    expect(payload.schema_version).toBe(COMPARE_EXPORT_SCHEMA_VERSION)
    expect(payload.base.run_id).toBe(BASE_RUN.id)
    expect(payload.target.run_id).toBe(TARGET_RUN.id)
    expect(payload.base.judge_model).toBe('qwen-flash')
    expect(payload.base.prompt_version).toBe('v1.2.5')
    expect(payload.comparison.same_config).toBe(true)
    expect(payload.comparison.noise_notice).toBe(COMPARE_EXPORT_NOISE_NOTICE)
    expect(payload.metrics).toHaveLength(3)
    expect(payload.cases).toHaveLength(120)
    expect(payload.case_summary).toMatchObject({
      improved: 31,
      regressed: 32,
      unchanged: 57,
      invalid: 0,
      unprocessed: 0,
      total: 120,
      exported_cases: 120,
      case_truncated: false,
    })
    expect(payload.cases[0]).toMatchObject({
      dataset_item_id: 'item-0',
      item_key: 'P12-000',
      verdict: 'improved',
      verdict_label: '变好',
      driver_metric: 'faithfulness',
    })
  })

  it('adapter 不同时 same_config=false', () => {
    const payload = payloadFor({ target: { ...TARGET_RUN, adapter: 'weknora' } })
    expect(payload.comparison.same_adapter).toBe(false)
    expect(payload.comparison.same_config).toBe(false)
    expect(payload.comparison.noise_notice).toContain('Judge 为 beta')
  })

  it('250 Case 只导出前 200 并带截断说明', () => {
    const rows = makeRows(250)
    const payload = payloadFor({
      rows,
      diffCounts: { ...DIFF_COUNTS, unchanged: 187 },
      alignedCount: 250,
      caseTruncated: true,
    })

    expect(payload.cases).toHaveLength(200)
    expect(payload.case_summary.case_truncated).toBe(true)
    expect(payload.case_summary.aligned_total).toBe(250)
    expect(payload.case_summary.truncation_note).toContain('仅导出前 200 个 Case')
  })
})

describe('toCompareCsv', () => {
  it('带 BOM、元数据与 noise_notice，Case 行数与页面一致', () => {
    const csv = toCompareCsv(payloadFor())

    expect(csv.startsWith('\ufeff')).toBe(true)
    expect(csv).toContain('# schema_version=m3.compare.export.v1')
    expect(csv).toContain('# same_config=true')
    expect(csv).toContain('# noise_notice=')
    expect(csv).toContain('Judge 为 beta')

    const { header, rows } = dataRows(csv)
    expect(header).toHaveLength(17)
    expect(rows).toHaveLength(120)
  })

  it('逗号/引号/换行/中文可正确 round-trip', () => {
    const csv = toCompareCsv(payloadFor())
    const parsed = parseCsv(csv.replace(/^\ufeff/, ''))
    const headerIndex = parsed.findIndex(row => row[0] === 'dataset_item_id')
    const values = parsed[headerIndex + 1]

    expect(values[2]).toBe('问题 0，含逗号、"引号" 与\n换行')
    expect(values[0]).toBe('item-0')
    expect(values[13]).toBe('变好')
    expect(values[14]).toBe('faithfulness')
  })

  it('200 上限时 CSV 只包含 200 行 Case', () => {
    const csv = toCompareCsv(
      payloadFor({
        rows: makeRows(250),
        diffCounts: { ...DIFF_COUNTS, unchanged: 187 },
        alignedCount: 250,
        caseTruncated: true,
      })
    )

    const { rows } = dataRows(csv)
    expect(rows).toHaveLength(200)
    expect(csv).toContain('# case_truncated=true')
    expect(csv).toContain('仅导出前 200 个 Case')
  })
})

describe('报告快照', () => {
  function rowWithDelta(index, status, driverDelta) {
    const row = makeRow(index, status)
    return {
      ...row,
      diff: {
        ...row.diff,
        driver: { name: 'faithfulness', short: 'F', delta: driverDelta },
        note: `F ${driverDelta > 0 ? '+' : ''}${driverDelta.toFixed(3)}`,
      },
    }
  }

  it('Top 变好/变差按驱动指标绝对变化排序，最多 5 条', () => {
    const rows = [
      rowWithDelta(0, 'improved', 0.1),
      rowWithDelta(1, 'improved', 0.5),
      rowWithDelta(2, 'improved', 0.3),
      rowWithDelta(3, 'improved', 0.7),
      rowWithDelta(4, 'improved', 0.2),
      rowWithDelta(5, 'improved', 0.6),
      rowWithDelta(6, 'regressed', -0.4),
      rowWithDelta(7, 'regressed', -0.8),
      rowWithDelta(8, 'unchanged', 0),
    ]
    const improved = topDiffCases(rows, 'improved', 5)
    const regressed = topDiffCases(rows, 'regressed', 5)

    expect(improved).toHaveLength(5)
    expect(improved.map(item => item.driver_delta)).toEqual([0.7, 0.6, 0.5, 0.3, 0.2])
    expect(improved[0]).toMatchObject({
      item_key: 'P12-003',
      verdict: 'improved',
      driver_metric: 'faithfulness',
    })
    expect(regressed.map(item => item.driver_delta)).toEqual([-0.8, -0.4])
  })

  it('空数据时 Top 为空，报告快照仍保留汇总与链接', () => {
    const payload = buildComparisonReportPayload({
      base: BASE_RUN,
      target: TARGET_RUN,
      metricRows: METRIC_ROWS,
      rows: [],
      diffCounts: {},
      alignedCount: 0,
      caseTruncated: false,
      compareUrl: '/rag-evaluations/compare?base=a&target=b',
    })

    expect(payload.top_improved).toEqual([])
    expect(payload.top_regressed).toEqual([])
    expect(payload.compare_url).toBe('/rag-evaluations/compare?base=a&target=b')
    expect(payload.case_summary.total).toBe(0)
  })

  it('报告快照含 Top 5 与 same_config/noise', () => {
    const payload = buildComparisonReportPayload({
      base: BASE_RUN,
      target: TARGET_RUN,
      metricRows: METRIC_ROWS,
      rows: makeRows(),
      diffCounts: DIFF_COUNTS,
      alignedCount: 120,
      caseTruncated: false,
      compareUrl: '/rag-evaluations/compare?base=a&target=b',
    })

    expect(payload.top_improved).toHaveLength(5)
    expect(payload.top_regressed).toHaveLength(5)
    expect(payload.same_config).toBe(true)
    expect(payload.comparison.same_config).toBe(true)
    expect(payload.comparison.noise_notice).toContain('Judge 为 beta')
    expect(payload.case_summary.improved).toBe(31)
  })
})

describe('JSON 与文件名', () => {
  it('JSON round-trip 保留 schema 与字段', () => {
    const payload = payloadFor()
    const parsed = JSON.parse(JSON.stringify(payload))

    expect(parsed.schema_version).toBe('m3.compare.export.v1')
    expect(parsed.base.run_id).toBe(BASE_RUN.id)
    expect(parsed.target.dataset_version_id).toBe('ver-1')
    expect(parsed.cases).toHaveLength(120)
    expect(parsed.cases[0].base_faithfulness).toBe(0.5)
    expect(parsed.cases[0].delta_answer_correctness).toBe(0)
  })

  it('文件名使用 base8/target8/timestamp', () => {
    const name = buildCompareExportFilename(
      'csv',
      BASE_RUN.id,
      TARGET_RUN.id,
      '2026-11-25T04:00:00.000Z'
    )
    expect(name).toBe('rag-compare_5328123c_7b2fa311_20261125T040000Z.csv')
    expect(name.endsWith('.csv')).toBe(true)
  })
})
