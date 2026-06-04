import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  PlaySquare,
  Music,
  Image as ImageIcon,
  Monitor,
  Settings,
  ChevronLeft,
  ChevronRight
} from 'lucide-react'
import useAuthStore from '@/store/authStore'

const menuItems = [
  {
    path: '/dashboard',
    icon: <LayoutDashboard size={20} />,
    label: '仪表盘',
  },
  {
    path: '/user',
    icon: <Users size={20} />,
    label: '用户管理',
  },
  {
    label: '内容管理',
    icon: <PlaySquare size={20} />,
    children: [
      { path: '/content/video', label: '视频管理', icon: <PlaySquare size={16} /> },
      { path: '/content/audio', label: '音频管理', icon: <Music size={16} /> },
      { path: '/content/image', label: '图片管理', icon: <ImageIcon size={16} /> },
    ],
  },
  {
    path: '/system/monitor',
    icon: <Monitor size={20} />,
    label: '系统监控',
  },
  {
    path: '/settings',
    icon: <Settings size={20} />,
    label: '系统设置',
  },
]

function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const [openMenus, setOpenMenus] = useState(['content'])
  const location = useLocation()
  const userInfo = useAuthStore((state) => state.userInfo)

  const toggleMenu = (key) => {
    setOpenMenus(prev =>
      prev.includes(key)
        ? prev.filter(item => item !== key)
        : [...prev, key]
    )
  }

  const isActive = (path) => {
    if (path === '/dashboard') {
      return location.pathname === path
    }
    return location.pathname.startsWith(path)
  }

  return (
    <div className={`h-screen bg-white border-r border-gray-100 transition-all duration-300 ${collapsed ? 'w-20' : 'w-64'}`}>
      {/* Logo区域 */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-gray-100">
        {!collapsed && (
          <h1 className="text-xl font-bold text-primary">VidMuse Admin</h1>
        )}
        {collapsed && <div className="w-full flex justify-center">
          <h1 className="text-xl font-bold text-primary">VM</h1>
        </div>}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-md hover:bg-gray-50 text-gray-400 hover:text-gray-500"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* 导航菜单 */}
      <nav className="p-2">
        {menuItems.map((item, index) => (
          <div key={index} className="mb-1">
            {item.children ? (
              <div>
                <button
                  onClick={() => toggleMenu(item.label)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    item.children.some(child => isActive(child.path))
                      ? 'bg-primary/10 text-primary'
                      : 'text-gray-500 hover:bg-gray-50 hover:text-gray-500'
                  }`}
                >
                  <div className="flex items-center">
                    <span className="mr-3">{item.icon}</span>
                    {!collapsed && <span>{item.label}</span>}
                  </div>
                  {!collapsed && (
                    <ChevronRight
                      size={16}
                      className={`transition-transform ${openMenus.includes(item.label) ? 'rotate-90' : ''}`}
                    />
                  )}
                </button>
                {!collapsed && openMenus.includes(item.label) && (
                  <div className="ml-4 mt-1">
                    {item.children.map((child, childIndex) => (
                      <NavLink
                        key={childIndex}
                        to={child.path}
                        className={({ isActive }) =>
                          `flex items-center px-3 py-2 rounded-md text-sm transition-colors ${
                            isActive
                              ? 'bg-primary/10 text-primary font-medium'
                              : 'text-gray-400 hover:bg-gray-50 hover:text-gray-500'
                          }`
                        }
                      >
                        <span className="mr-3">{child.icon}</span>
                        <span>{child.label}</span>
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-gray-500 hover:bg-gray-50 hover:text-gray-500'
                  }`
                }
              >
                <span className="mr-3">{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            )}
          </div>
        ))}
      </nav>

      {/* 底部用户信息 */}
      {!collapsed && (
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-100">
          <div className="flex items-center">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
              {userInfo?.name?.charAt(0) || 'A'}
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-500">{userInfo?.name || 'Admin'}</p>
              <p className="text-xs text-gray-300">超级管理员</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Sidebar
