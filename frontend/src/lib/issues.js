/**
 * 清洗 / 评估 issues 的中文标签（后端返回的是稳定英文码）。
 * 未收录的码原样展示，避免前端漏更新导致信息丢失。
 */
export const ISSUE_LABELS = {
  asr_transcript: '来自 ASR 转写',
  asr_transcript_uncertain: 'ASR 转写可能不准',
  mono_speaker_unknown: '单声道，说话人未知',
  dual_mono: '双声道同源',
  speaker_inferred: '说话人由模型推断',
  relative_timestamp: '时间为相对偏移',
  missing_user_message: '缺少用户消息',
  missing_ai_response: '缺少 AI 回复',
  duplicate: '疑似重复',
  structure_unparsed: '未切分问答（整段保留）',
  structure_partial: '部分内容未切分',
  answer_evasive: '回答回避问题',
  answer_incomplete: '回答不完整',
  off_topic: '回答跑题',
}

/**
 * @param {string} code 后端 issue 码
 * @returns {string} 中文标签；未知码原样返回
 */
export function issueLabel(code) {
  const key = String(code || '')
  return ISSUE_LABELS[key] || key
}

/** 结构化失败/不完整：需要在界面上给出「可重试拆分」提示。 */
export function hasStructureIssue(issues = []) {
  return issues.some(code => code === 'structure_unparsed' || code === 'structure_partial')
}
