import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { queryClient } from './lib/queryClient'
import { initSentry } from './lib/sentry'
import { ToastContainer } from './components/Toast'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { AppRoutes, preloadRoutes } from './router'
import { useAuthStore } from './stores/authStore'
import './index.css'

useAuthStore.getState().hydrate()
// T7：VITE_SENTRY_DSN 为空时 no-op
initSentry()

// 空闲时预取业务路由 chunk：首次切换栏目不再出现加载空白
if (typeof window !== 'undefined') {
  const schedule = () => preloadRoutes()
  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(schedule, { timeout: 3000 })
  } else {
    window.setTimeout(schedule, 1500)
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true }}>
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
        <ToastContainer />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
)
