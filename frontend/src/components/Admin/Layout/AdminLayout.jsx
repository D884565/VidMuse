import { Outlet } from 'react-router-dom'

export default function AdminLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="p-8">
        <h1 className="text-2xl font-bold mb-4">管理员后台（开发中）</h1>
        <Outlet />
      </div>
    </div>
  )
}
