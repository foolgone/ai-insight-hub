import { describe, expect, it } from 'vitest'
import { hasStructureIssue, issueLabel, ISSUE_LABELS } from './issues'

describe('issues 映射', () => {
  it('已知问题码翻成中文', () => {
    expect(issueLabel('structure_unparsed')).toBe('未切分问答（整段保留）')
    expect(issueLabel('knowledge_base_empty')).toBe('knowledge_base_empty')
  })

  it('未收录的码原样返回，不透传 undefined', () => {
    expect(issueLabel('some_future_code')).toBe('some_future_code')
    expect(issueLabel(undefined)).toBe('')
  })

  it('结构化问题识别', () => {
    expect(hasStructureIssue(['asr_transcript', 'structure_partial'])).toBe(true)
    expect(hasStructureIssue(['asr_transcript'])).toBe(false)
    expect(hasStructureIssue()).toBe(false)
  })

  it('文案表包含后端的稳定码', () => {
    expect(ISSUE_LABELS.structure_unparsed).toBeTruthy()
    expect(ISSUE_LABELS.answer_incomplete).toBeTruthy()
  })
})
