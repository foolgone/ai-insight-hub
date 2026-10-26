import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { queryClient } from './lib/queryClient'
import { initSentry } from './lib/sentry'
import { ToastContainer } from './components/Toast'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { AppRoutes } from './router'
import { useAuthStore } from './stores/authStore'
import './index.css'

useAuthStore.getState().hydrate()
// T7：VITE_SENTRY_DSN 为空时 no-op
initSentry()

ReactDOM.createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
        <ToastContainer />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
)
