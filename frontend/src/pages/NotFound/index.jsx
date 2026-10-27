import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-6 text-center">
      <p className="text-5xl font-bold text-primary-500">404</p>
      <h1 className="mt-4 text-xl font-semibold text-gray-900">页面不存在</h1>
      <p className="mt-2 text-sm text-gray-500">访问的地址不存在或已被移除。</p>
      <Link
        to="/dashboard"
        className="mt-6 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
      >
        返回 Dashboard
      </Link>
    </main>
  )
}
