import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PublicOnlyRoute } from './components/auth/PublicOnlyRoute'
import { AppLayout } from './components/layout/AppLayout'
import { PageLoading } from './components/common/PageLoading'

/**
 * 懒加载 + 可预加载：路由 chunk 在空闲时提前拉取，切换栏目不再等网络。
 */
function lazyWithPreload(factory) {
  const Component = lazy(factory)
  Component.preload = factory
  return Component
}

const Login = lazyWithPreload(() => import('./pages/Login'))
const Dashboard = lazyWithPreload(() => import('./pages/Dashboard'))
const DataSources = lazyWithPreload(() => import('./pages/DataSources'))
const DataCleaning = lazyWithPreload(() => import('./pages/DataCleaning'))
const QualityAssessment = lazyWithPreload(() => import('./pages/QualityAssessment'))
const QualityAssessmentDetail = lazyWithPreload(() => import('./pages/QualityAssessment/Detail'))
const KnowledgeBase = lazyWithPreload(() => import('./pages/KnowledgeBase'))
const Reports = lazyWithPreload(() => import('./pages/Reports'))
const NotFound = lazyWithPreload(() => import('./pages/NotFound'))

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

/** 路由表（D-F06 / §7.1）：8 个业务路由 + 404。 */
export function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-screen place-items-center bg-gray-50">
          <PageLoading label="正在加载..." />
        </div>
      }
    >
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<Login />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="data-sources" element={<DataSources />} />
            <Route path="data-cleaning" element={<DataCleaning />} />
            <Route path="quality-assessment" element={<QualityAssessment />} />
            <Route path="quality-assessment/:id" element={<QualityAssessmentDetail />} />
            <Route path="knowledge-base" element={<KnowledgeBase />} />
            <Route path="reports" element={<Reports />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
