import { useEffect, useState } from 'react'
import { Modal } from '../Modal'
import { Tabs } from '../Tabs'
import { LlmKeyPanel } from './LlmKeyPanel'
import { AsrKeyPanel } from './AsrKeyPanel'

const TAB_ITEMS = [
  { key: 'llm', label: '模型 API Key' },
  { key: 'asr', label: '语音转写' },
]

const TITLES = {
  llm: '模型 API Key 设置',
  asr: '语音转写设置',
}

/**
 * 凭据设置弹窗（需求 §8 + 音视频 ASR 扩展）。
 * 两个标签页共用同一套加密存储与审计：模型 API Key / 语音转写。
 * @param {{ open: boolean, onClose: () => void, isDemo?: boolean, initialTab?: 'llm'|'asr' }} props
 */
export function APIKeyModal({ open, onClose, isDemo = false, initialTab = 'llm' }) {
  const [tab, setTab] = useState(initialTab)

  // 每次打开按入口定位（428 拦截器会把用户直接送到对应页）
  useEffect(() => {
    if (open) setTab(initialTab || 'llm')
  }, [open, initialTab])

  return (
    <Modal open={open} onClose={onClose} title={TITLES[tab] || TITLES.llm} size="md">
      <Tabs items={TAB_ITEMS} value={tab} onChange={setTab} className="mb-4" />
      {tab === 'asr' ? <AsrKeyPanel /> : <LlmKeyPanel isDemo={isDemo} />}
    </Modal>
  )
}
