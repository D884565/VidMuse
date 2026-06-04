import { Link } from 'react-router-dom'

export default function Forbidden() {
  return (
    <div className="min-h-screen bg-[var(--bg-main)] flex flex-col items-center justify-center text-white">
      <h1 className="text-6xl font-bold mb-4">403</h1>
      <p className="text-xl mb-8 text-gray-400">无权限访问此页面</p>
      <Link
        to="/"
        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
      >
        返回首页
      </Link>
    </div>
  )
}
