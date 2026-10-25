import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const COMPONENTS = {
  h1: props => <h1 className="mb-2 mt-4 text-lg font-bold text-gray-900" {...props} />,
  h2: props => <h2 className="mb-2 mt-4 text-base font-semibold text-gray-900" {...props} />,
  h3: props => <h3 className="mb-1 mt-3 text-sm font-semibold text-gray-900" {...props} />,
  p: props => <p className="mb-2 leading-6" {...props} />,
  ul: props => <ul className="mb-2 list-inside list-disc pl-2" {...props} />,
  ol: props => <ol className="mb-2 list-inside list-decimal pl-2" {...props} />,
  li: props => <li className="mb-0.5" {...props} />,
  a: props => (
    <a
      {...props}
      target="_blank"
      rel="noreferrer"
      className="text-primary-600 underline hover:text-primary-700"
    />
  ),
  code: ({ inline, children, ...props }) =>
    inline ? (
      <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs text-gray-800" {...props}>
        {children}
      </code>
    ) : (
      <code
        className="block overflow-x-auto rounded bg-gray-100 p-2 font-mono text-xs text-gray-800"
        {...props}
      >
        {children}
      </code>
    ),
  pre: props => <pre className="mb-2" {...props} />,
  table: props => (
    <div className="mb-2 overflow-x-auto">
      <table className="min-w-full border-collapse text-xs" {...props} />
    </div>
  ),
  th: props => (
    <th className="border border-gray-300 bg-gray-50 px-2 py-1 text-left font-medium" {...props} />
  ),
  td: props => <td className="border border-gray-300 px-2 py-1" {...props} />,
  blockquote: props => (
    <blockquote className="mb-2 border-l-4 border-gray-300 pl-3 text-gray-500" {...props} />
  ),
}

/**
 * Markdown 只读渲染（F-401）：GFM + 禁用原始 HTML（D-F03，防 XSS）。
 * @param {{ children?: string, className?: string }} props
 */
export function Markdown({ children = '', className }) {
  return (
    <div className={clsx('text-sm text-gray-700', className)}>
      <ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {String(children || '')}
      </ReactMarkdown>
    </div>
  )
}
