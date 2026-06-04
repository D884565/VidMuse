import { Link } from 'react-router-dom'

function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <h1 className="text-6xl font-bold text-gray-300 mb-4">404</h1>
      <p className="text-xl text-gray-500 mb-8">页面不存在</p>
      <Link to="/dashboard" className="btn-primary">
        返回首页
      </Link>
    </div>
  )
}

export default NotFound
