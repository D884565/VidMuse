import { NavLink, useLocation } from 'react-router-dom'
import {
  Users,
  FileImage,
  Settings,
  LogOut,
  FolderTree,
  Image,
  Video,
  Lightbulb,
  Activity,
  Server
} from 'lucide-react'
import { useAppStore } from '../../../store/appStore'

const menuItems = [
  { path: '/admin/users', icon: Users, label: '用户管理' },
  { path: '/admin/categories', icon: FolderTree, label: '分类管理' },
  { path: '/admin/assets', icon: Image, label: '资产管理' },
  { path: '/admin/videos', icon: Video, label: '视频库' },
  { path: '/admin/inspiration', icon: Lightbulb, label: '灵感模板' },
  { path: '/admin/traces', icon: Activity, label: 'Agent链路追踪' },
  { path: '/admin/system-traces', icon: Server, label: '系统链路追踪' },
]

export default function AdminSidebar() {
  const location = useLocation()
  const logout = useAppStore((state) => state.logout)

  return (
    <div className="fixed left-0 top-0 h-screen w-64 bg-gray-900 text-white flex flex-col">
      <div className="p-6 border-b border-gray-800">
        <h1 className="text-xl font-bold">VidMuse 管理后台</h1>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <item.icon size={20} />
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <button
          onClick={logout}
          className="flex items-center space-x-3 px-4 py-3 w-full rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <LogOut size={20} />
          <span>退出登录</span>
        </button>
      </div>
    </div>
  )
}
