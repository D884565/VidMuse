import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Search, User, LogOut, Settings as SettingsIcon } from 'lucide-react'
import useAuthStore from '@/store/authStore'

function Header() {
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const navigate = useNavigate()
  const { userInfo, logout } = useAuthStore()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <header className="h-16 bg-white border-b border-gray-100 px-6 flex items-center justify-between">
      {/* 面包屑占位 - 实际项目中可以实现动态面包屑 */}
      <div className="flex items-center">
        <div className="text-sm text-gray-400">
          {/* Breadcrumb will be here */}
        </div>
      </div>

      {/* 右侧工具栏 */}
      <div className="flex items-center space-x-4">
        {/* 搜索框 */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-300" size={16} />
          <input
            type="text"
            placeholder="搜索..."
            className="pl-10 pr-4 py-2 rounded-md border border-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary w-64"
          />
        </div>

        {/* 通知图标 */}
        <button className="p-2 rounded-md hover:bg-gray-50 text-gray-400 hover:text-gray-500 relative">
          <Bell size={20} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-danger rounded-full"></span>
        </button>

        {/* 用户菜单 */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center space-x-2 p-2 rounded-md hover:bg-gray-50"
          >
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium text-sm">
              {userInfo?.name?.charAt(0) || 'A'}
            </div>
            <span className="text-sm font-medium text-gray-500">{userInfo?.name || 'Admin'}</span>
          </button>

          {userMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setUserMenuOpen(false)}
              />
              <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-md shadow-lg border border-gray-100 z-20 py-1">
                <button
                  onClick={() => {
                    setUserMenuOpen(false)
                    // 跳转到个人信息页
                  }}
                  className="w-full flex items-center px-4 py-2 text-sm text-gray-500 hover:bg-gray-50"
                >
                  <User size={16} className="mr-2" />
                  个人信息
                </button>
                <button
                  onClick={() => {
                    setUserMenuOpen(false)
                    navigate('/settings')
                  }}
                  className="w-full flex items-center px-4 py-2 text-sm text-gray-500 hover:bg-gray-50"
                >
                  <SettingsIcon size={16} className="mr-2" />
                  系统设置
                </button>
                <hr className="my-1 border-gray-100" />
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center px-4 py-2 text-sm text-danger hover:bg-gray-50"
                >
                  <LogOut size={16} className="mr-2" />
                  退出登录
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

export default Header
