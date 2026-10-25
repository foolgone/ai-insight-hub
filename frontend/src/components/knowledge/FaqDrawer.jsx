import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Drawer } from '../Drawer'
import { Input } from '../Input'
import { Textarea } from '../Textarea'
import { Markdown } from '../common/Markdown'
import { useCreateFaq, useUpdateFaq } from '../../hooks/useKnowledge'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

/**
 * FAQ 新建/编辑 Drawer（F-404）：问题/答案/分类/标签 + Markdown 预览。
 * @param {{ open: boolean, onClose: () => void, datasourceId: string|null, faq?: Object|null, prefillQuestion?: string }} props
 */
export function FaqDrawer({ open, onClose, datasourceId, faq = null, prefillQuestion = '' }) {
  const createMutation = useCreateFaq()
  const updateMutation = useUpdateFaq()
  const isEdit = Boolean(faq)

  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [category, setCategory] = useState('')
  const [tags, setTags] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setQuestion(faq?.question || prefillQuestion || '')
    setAnswer(faq?.answer || '')
    setCategory(faq?.category || '')
    setTags(Array.isArray(faq?.tags) ? faq.tags.join(', ') : '')
    setError('')
  }, [open, faq, prefillQuestion])

  const pending = createMutation.isPending || updateMutation.isPending

  const handleSubmit = async () => {
    if (!datasourceId) {
      setError('请先选择数据源')
      return
    }
    if (!question.trim()) {
      setError('请输入问题')
      return
    }
    if (!answer.trim()) {
      setError('请输入答案')
      return
    }

    const payload = {
      question: question.trim(),
      answer: answer.trim(),
      ...(category.trim() ? { category: category.trim() } : {}),
      tags: tags
        .split(',')
        .map(tag => tag.trim())
        .filter(Boolean),
    }

    try {
      if (isEdit) {
        await updateMutation.mutateAsync({ datasourceId, faqId: faq.id, payload })
        notify.success('知识条目已更新')
      } else {
        await createMutation.mutateAsync({ datasourceId, payload })
        notify.success('知识条目已创建')
      }
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={isEdit ? '编辑知识条目' : '新建知识条目'}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={pending} disabled={pending}>
            保存
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
          <label htmlFor="faq-question" className="mb-1 block text-sm font-medium text-gray-700">
            问题 <span className="text-error-500">*</span>
          </label>
          <Input
            id="faq-question"
            value={question}
            onChange={setQuestion}
            placeholder="如：如何申请退款？"
            disabled={pending}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <label htmlFor="faq-answer" className="mb-1 block text-sm font-medium text-gray-700">
              答案 <span className="text-error-500">*</span>
            </label>
            <Textarea
              id="faq-answer"
              value={answer}
              onChange={setAnswer}
              rows={10}
              placeholder="支持 Markdown，右侧实时预览"
              disabled={pending}
            />
          </div>
          <div>
            <span className="mb-1 block text-sm font-medium text-gray-700">预览</span>
            <div className="h-[250px] overflow-y-auto rounded border border-gray-200 bg-gray-50 p-3">
              {answer.trim() ? (
                <Markdown>{answer}</Markdown>
              ) : (
                <p className="text-sm text-gray-400">输入答案后展示 Markdown 预览。</p>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="faq-category" className="mb-1 block text-sm font-medium text-gray-700">
              分类
            </label>
            <Input
              id="faq-category"
              value={category}
              onChange={setCategory}
              placeholder="如：售后"
              disabled={pending}
            />
          </div>
          <div>
            <label htmlFor="faq-tags" className="mb-1 block text-sm font-medium text-gray-700">
              标签（逗号分隔）
            </label>
            <Input
              id="faq-tags"
              value={tags}
              onChange={setTags}
              placeholder="退款, 售后"
              disabled={pending}
            />
          </div>
        </div>
      </div>
    </Drawer>
  )
}
