import { lazy } from 'react'

/**
 * 懒加载 + 可预加载：路由 chunk 在空闲时提前拉取，切换栏目不再等网络。
 * 独立成文件是为了让 `router.jsx` 只导出组件（react-refresh 要求）。
 */
export function lazyWithPreload(factory) {
  const Component = lazy(factory)
  Component.preload = factory
  return Component
}

export const Login = lazyWithPreload(() => import('../pages/Login'))
export const Dashboard = lazyWithPreload(() => import('../pages/Dashboard'))
export const DataSources = lazyWithPreload(() => import('../pages/DataSources'))
export const DataCleaning = lazyWithPreload(() => import('../pages/DataCleaning'))
export const QualityAssessment = lazyWithPreload(() => import('../pages/QualityAssessment'))
export const QualityAssessmentDetail = lazyWithPreload(
  () => import('../pages/QualityAssessment/Detail')
)
export const KnowledgeBase = lazyWithPreload(() => import('../pages/KnowledgeBase'))
export const Reports = lazyWithPreload(() => import('../pages/Reports'))
export const NotFound = lazyWithPreload(() => import('../pages/NotFound'))

const ROUTE_COMPONENTS = [
  Dashboard,
  DataSources,
  DataCleaning,
  QualityAssessment,
  QualityAssessmentDetail,
  KnowledgeBase,
  Reports,
  NotFound,
]

/** 空闲时预取业务路由 chunk（失败静默，不阻塞主流程）。 */
export function preloadRoutes() {
  for (const component of ROUTE_COMPONENTS) {
    component.preload().catch(() => {})
  }
}
