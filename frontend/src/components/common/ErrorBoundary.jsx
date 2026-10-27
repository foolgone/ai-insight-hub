import { Component } from 'react'
import { captureException } from '../../lib/sentry'

/**
 * 渲染异常兜底（F-105）：防止单页报错导致整站白屏；T7 起同时上报 Sentry。
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    captureException(error, { componentStack: info?.componentStack })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="flex min-h-screen flex-col items-center justify-center gap-3 bg-gray-50 p-6 text-center"
        >
          <h1 className="text-lg font-semibold text-gray-900">页面出错了</h1>
          <p className="text-sm text-gray-500">请刷新页面重试；若持续出现，请联系管理员。</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            刷新页面
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
