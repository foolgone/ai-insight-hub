/**
 * 页面头部（编辑部风格）：编号 + 等宽眉题 + 衬线大标题 + 右侧操作。
 * @param {{
 *   index?: string,
 *   eyebrow?: string,
 *   title: React.ReactNode,
 *   description?: React.ReactNode,
 *   actions?: React.ReactNode,
 * }} props
 */
export function PageHeader({ index, eyebrow, title, description, actions }) {
  const hasMeta = Boolean(index || eyebrow)
  return (
    <header className="flex flex-col gap-5 border-b border-gray-300 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {hasMeta ? (
          <p className="eyebrow">
            {index ? <span className="text-primary-600">{index}</span> : null}
            {index && eyebrow ? (
              <span className="mx-2 text-gray-300" aria-hidden="true">
                /
              </span>
            ) : null}
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mt-2 font-display text-3xl font-normal leading-tight tracking-tight text-gray-900 lg:text-[40px]">
          {title}
        </h1>
        {description ? (
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-gray-600">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}
