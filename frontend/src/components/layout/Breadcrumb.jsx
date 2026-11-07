import { Link, useLocation } from 'react-router-dom'

const ROOT_LABELS = {
  dashboard: 'Dashboard',
  'data-sources': '数据源管理',
  'data-cleaning': '数据清洗',
  'quality-assessment': '质量评估',
  'knowledge-base': '知识库',
  reports: '报告中心',
}

/**
 * 顶部面包屑：一级取路由段映射，二级（详情页 id）显示「详情」。
 */
export function Breadcrumb() {
  const { pathname } = useLocation()
  const segments = pathname.split('/').filter(Boolean)
  if (segments.length === 0) return null

  const [root, child] = segments
  const rootLabel = ROOT_LABELS[root] || root
  const hasChild = Boolean(child)

  return (
    <nav
      aria-label="面包屑"
      className="flex min-w-0 items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em]"
    >
      {hasChild ? (
        <Link
          to={`/${root}`}
          className="truncate text-gray-500 transition-colors hover:text-gray-900"
        >
          {rootLabel}
        </Link>
      ) : (
        <span className="truncate text-gray-900">{rootLabel}</span>
      )}
      {hasChild ? (
        <>
          <span className="text-gray-400" aria-hidden="true">
            /
          </span>
          <span className="truncate text-gray-700">详情</span>
        </>
      ) : null}
    </nav>
  )
}
