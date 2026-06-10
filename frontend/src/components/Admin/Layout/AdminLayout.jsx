import { Outlet } from 'react-router-dom'
import AdminSidebar from './AdminSidebar'
import AdminHeader from './AdminHeader'

/** 管理后台布局 — 左侧边栏 + 顶部导航 + 内容区域（通过 Outlet 渲染子路由） */
export default function AdminLayout() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <AdminSidebar />
      <div className="ml-64">
        <AdminHeader />
        <main className="min-h-[calc(100vh-4rem)] p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
