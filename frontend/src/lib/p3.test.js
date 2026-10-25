import { afterEach, describe, expect, it, vi } from 'vitest'
import { countQualityLevels, qualityLevelForScore, QUALITY_LEVELS } from './quality'
import { dimensionLabel, EVALUATION_DIMENSIONS } from './evaluation'
import { downloadTextFile, toCsv } from './download'

describe('quality helpers', () => {
  it('按分数映射 fair/poor 等 4 档', () => {
    expect(qualityLevelForScore(95).key).toBe('excellent')
    expect(qualityLevelForScore(75).key).toBe('good')
    expect(qualityLevelForScore(60).key).toBe('fair')
    expect(qualityLevelForScore(59).key).toBe('poor')
    expect(qualityLevelForScore(999).key).toBe('excellent')
    expect(QUALITY_LEVELS).toHaveLength(4)
  })

  it('统计 4 档分布', () => {
    const distribution = countQualityLevels([
      { overall_score: 95 },
      { overall_score: 80 },
      { overall_score: 80 },
      { overall_score: 60 },
      { overall_score: 20 },
    ])

    expect(distribution.map(item => item.value)).toEqual([1, 2, 1, 1])
  })
})

describe('evaluation helpers', () => {
  it('维度中文名与顺序', () => {
    expect(EVALUATION_DIMENSIONS).toHaveLength(5)
    expect(dimensionLabel('accuracy')).toBe('准确性')
    expect(dimensionLabel('unknown')).toBe('unknown')
  })
})

describe('download helpers', () => {
  afterEach(() => vi.restoreAllMocks())

  it('toCsv 转义引号与逗号', () => {
    const csv = toCsv([
      ['名称', '说明'],
      ['退款,加急', '含"引号"'],
    ])

    expect(csv).toBe('"名称","说明"\r\n"退款,加急","含""引号"""')
  })

  it('downloadTextFile 创建 Blob 并触发下载', () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:mock')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    downloadTextFile('a.csv', 'x')

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(click).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})
