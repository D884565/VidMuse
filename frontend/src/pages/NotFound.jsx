import { Link, useLocation } from 'react-router-dom'

export default function NotFound() {
  const location = useLocation()
  const isAdminRoute = location.pathname.startsWith('/admin')

  return (
    <div className={`min-h-screen flex flex-col items-center justify-center ${
      isAdminRoute ? 'bg-gray-50 text-gray-900' : 'bg-[var(--bg-main)] text-white'
    }`}>
      <h1 className="text-6xl font-bold mb-4">404</h1>
      <p className={`text-xl mb-8 ${isAdminRoute ? 'text-gray-600' : 'text-gray-400'}`}>
        页面不存在
      </p>
      <Link
        to="/"
        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
      >
        返回首页
      </Link>
    </div>
  )
}
