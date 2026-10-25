/**
 * 页面占位（P0 骨架期使用，后续阶段由真实页面替换）。
 * @param {{ title: string, description?: string }} props
 */
export function PagePlaceholder({ title, description }) {
  return (
    <section>
      <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">{title}</h1>
      {description ? <p className="mt-2 text-sm text-gray-500">{description}</p> : null}
      <div className="mt-6 rounded-md border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
        页面骨架已就绪，功能将在后续阶段实现。
      </div>
    </section>
  )
}
