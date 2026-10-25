import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PublicOnlyRoute } from './components/auth/PublicOnlyRoute'
import { AppLayout } from './components/layout/AppLayout'

const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const DataSources = lazy(() => import('./pages/DataSources'))
const DataCleaning = lazy(() => import('./pages/DataCleaning'))
const QualityAssessment = lazy(() => import('./pages/QualityAssessment'))
const QualityAssessmentDetail = lazy(() => import('./pages/QualityAssessment/Detail'))
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'))
const Reports = lazy(() => import('./pages/Reports'))
const NotFound = lazy(() => import('./pages/NotFound'))

/** 路由表（D-F06 / §7.1）：8 个业务路由 + 404。 */
export function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div role="status" className="p-8 text-sm text-gray-500">
          加载中...
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
