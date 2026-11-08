import { Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PublicOnlyRoute } from './components/auth/PublicOnlyRoute'
import { AppLayout } from './components/layout/AppLayout'
import { PageLoading } from './components/common/PageLoading'
import {
  Dashboard,
  DataCleaning,
  DataSources,
  KnowledgeBase,
  Login,
  NotFound,
  QualityAssessment,
  QualityAssessmentDetail,
  Reports,
} from './lib/routeComponents'

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
