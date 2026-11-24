import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LuArrowLeft } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { Badge } from '../../components/Badge'
import { RagBetaNotice } from '../../components/rag/RagBetaNotice'
import {
  useDatasetItemQuery,
  useRagEvaluationQuery,
  useRagEvaluationResultsQuery,
  useRagTraceQuery,
} from '../../hooks/useRagEvaluations'
import { formatDateTime } from '../../lib/format'
import {
  claimSupportMeta,
  claimsOf,
  formatScore,
  invalidReasonLabel,
  metricLabel,
  quotesOf,
  resultStatusMeta,
  shortId,
} from '../../lib/ragEvaluation'

function Section({ title, description, children }) {
  return (
    <section className="rounded-md border border-gray-200 bg-white p-4">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {description ? <p className="mt-1 text-xs text-gray-500">{description}</p> : null}
      </div>
      {children}
    </section>
  )
}

export default function RagEvaluationCaseDetail() {
  const { runId, itemId } = useParams()
  const runQuery = useRagEvaluationQuery(runId)
  const run = runQuery.data

  const resultsQuery = useRagEvaluationResultsQuery(runId, {
    limit: 100,
    dataset_item_id: itemId,
  })
  const itemQuery = useDatasetItemQuery(
    run?.dataset_id,
    run?.dataset_version_id,
    itemId
  )

  const results = resultsQuery.data?.items || []
  const traceId = results.find(row => row.trace_id)?.trace_id
  const traceQuery = useRagTraceQuery(traceId)

  const faithfulness = results.find(row => row.metric_name === 'faithfulness')
  const claims = useMemo(() => claimsOf(faithfulness), [faithfulness])
  const item = itemQuery.data
  const trace = traceQuery.data

  if (runQuery.isLoading || resultsQuery.isLoading) {
    return <PageLoading label="正在加载 Case 详情..." />
  }
  if (runQuery.isError) {
    return <AsyncState error={runQuery.error} onRetry={() => runQuery.refetch()} />
  }
  if (resultsQuery.isError) {
    return <AsyncState error={resultsQuery.error} onRetry={() => resultsQuery.refetch()} />
  }
  if (!results.length) {
    return (
      <section className="space-y-4">
        <Link to={`/rag-evaluations/${runId}`} className="text-sm text-primary-600">
          返回 Run 详情
        </Link>
        <p className="rounded-md border border-dashed border-gray-300 bg-white p-6 text-sm text-gray-500">
          该 Case 在本 Run 中没有指标结果。
        </p>
      </section>
    )
  }

  const hasInvalid = results.some(row => row.status === 'invalid')
  const issueRows = results.filter(row => row.status !== 'evaluated')

  return (
    <section className="space-y-6">
      <div>
        <Link
          to={`/rag-evaluations/${runId}`}
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <LuArrowLeft className="h-4 w-4" aria-hidden="true" />
          返回 Run 详情
        </Link>
        <div className="mt-2">
          <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">Case 详情</h1>
          <p className="mt-1 text-xs text-gray-500">
            Run {shortId(runId)} · item {shortId(itemId)} ·{' '}
            {item?.item_key ? `${item.item_key} · ` : ''}
            {item?.category || '未分类'}
          </p>
        </div>
      </div>

      <RagBetaNotice
        issues={issueRows.map(row => ({
          key: row.id,
          label: `${metricLabel(row.metric_name)} ${row.status}`,
          count: 1,
        }))}
      />

      <Section
        title="问题与答案"
        description="question / answer 来自本次 RAG Trace；gold_answer 来自数据集，仅作参考。"
      >
        <div className="space-y-4">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-gray-400">Question</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-900">
              {trace?.query || item?.query || '—'}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-gray-400">Answer（RAG）</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-900">
              {trace?.answer || '—（本次 Trace 没有 answer）'}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-gray-400">Gold answer</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-600">
              {item?.gold_answer || '—'}
            </p>
          </div>
        </div>
      </Section>

      <Section
        title="Contexts"
        description={
          trace?.retrieved_contexts?.length
            ? '检索上下文（按 rank 排序）。quote 校验以这些文本为准。'
            : '本次 Trace 没有落库上下文；无法展示或复核 quote 来源。'
        }
      >
        {trace?.retrieved_contexts?.length ? (
          <ol className="space-y-3">
            {trace.retrieved_contexts.map((context, index) => (
              <li key={`${context.chunk_id || context.document_id || index}`} className="rounded border border-gray-100 bg-gray-50 p-3">
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
                  <Badge size="sm">C{context.rank ?? index + 1}</Badge>
                  {context.title ? <span>{context.title}</span> : null}
                  {typeof context.score === 'number' ? (
                    <span>score {formatScore(context.score, 3)}</span>
                  ) : null}
                  {context.chunk_id ? (
                    <span className="font-mono">chunk {shortId(context.chunk_id)}</span>
                  ) : null}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-gray-800">
                  {context.content}
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-gray-500">—</p>
        )}
      </Section>

      <Section title="指标结果" description="每个指标单独保留 status；invalid 不计入均值。">
        <div className="grid gap-3 sm:grid-cols-3">
          {results.map(row => {
            const meta = resultStatusMeta(row.status)
            return (
              <div key={row.id} className="rounded border border-gray-100 bg-gray-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-gray-700">
                    {metricLabel(row.metric_name)}
                  </p>
                  <Badge variant={meta.variant} size="sm">
                    {meta.label}
                  </Badge>
                </div>
                <p className="mt-2 text-2xl font-bold text-gray-900">
                  {formatScore(row.score, 3)}
                </p>
                {row.status !== 'evaluated' ? (
                  <p className="mt-1 text-[11px] text-warning-700">
                    {invalidReasonLabel(row.invalid_reason || row.error_message)}
                  </p>
                ) : null}
                <p className="mt-1 font-mono text-[10px] text-gray-400">
                  {row.metric_version} · {row.latency_ms ?? '—'}ms
                </p>
              </div>
            )
          })}
        </div>
      </Section>

      <Section
        title="Claims / Evidence"
        description="Faithfulness 的 claim 明细；quote 必须与 Contexts 连续匹配。"
      >
        {claims.length === 0 ? (
          <p className="text-sm text-gray-500">
            没有可展示的 claims（可能是 skipped / invalid，或该指标未返回明细）。
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-[11px] uppercase tracking-wide text-gray-400">
                  <th className="py-2 pr-3">ID</th>
                  <th className="py-2 pr-3">类型</th>
                  <th className="py-2 pr-3">支持状态</th>
                  <th className="py-2 pr-3">Claim</th>
                  <th className="py-2">Evidence quotes</th>
                </tr>
              </thead>
              <tbody>
                {claims.map((claim, index) => {
                  const support = claimSupportMeta(claim.support_status)
                  const quotes = quotesOf(claim)
                  return (
                    <tr key={claim.claim_id || index} className="border-b border-gray-100 align-top">
                      <td className="py-2 pr-3 font-mono text-[11px] text-gray-500">
                        {claim.claim_id || `cl${index + 1}`}
                      </td>
                      <td className="py-2 pr-3 text-xs text-gray-600">
                        {claim.claim_type || '—'}
                        <br />
                        <span className="text-[11px] text-gray-400">
                          {claim.claim_subtype || '—'}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        <Badge variant={support.variant} size="sm">
                          {support.label}
                        </Badge>
                        {claim.is_contradictory ? (
                          <p className="mt-1 text-[11px] text-error-700">contradictory</p>
                        ) : null}
                      </td>
                      <td className="max-w-md py-2 pr-3 text-xs text-gray-800">
                        {claim.claim || '—'}
                      </td>
                      <td className="py-2 text-xs text-gray-600">
                        {quotes.length ? (
                          <ul className="space-y-1">
                            {quotes.map((quote, quoteIndex) => (
                              <li
                                key={`${claim.claim_id}-${quoteIndex}`}
                                className="rounded bg-gray-50 px-2 py-1 text-[11px]"
                              >
                                “{quote}”
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {hasInvalid ? (
        <Section title="已知限制" description="本 Case 至少一个指标未通过 Judge 契约。">
          <ul className="space-y-2 text-sm">
            {issueRows.map(row => (
              <li key={row.id}>
                <span className="font-medium text-gray-900">{metricLabel(row.metric_name)}</span>
                <span className="ml-2 text-xs text-warning-700">
                  {invalidReasonLabel(row.invalid_reason || row.error_message)}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {faithfulness?.raw_output ? (
        <Section title="Raw output" description="Judge 原始输出（截断标记见 raw_truncated）。">
          <details>
            <summary className="cursor-pointer text-xs text-gray-500">
              展开原始输出{faithfulness.raw_truncated ? '（已截断）' : ''}
            </summary>
            <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded bg-gray-900 p-3 text-[11px] text-gray-100">
              {faithfulness.raw_output}
            </pre>
          </details>
        </Section>
      ) : null}

      <p className="text-[11px] text-gray-400">
        结果生成于 {formatDateTime(results[0]?.created_at)}；Judge beta，人工复核可覆盖。
      </p>
    </section>
  )
}
