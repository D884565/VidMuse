import { Bell, User, Settings } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'

export default function AdminHeader() {
  const user = useAppStore((state) => state.user)

  return (
    <div className="h-16 bg-white border-b border-gray-200 px-6 flex items-center justify-between shadow-sm">
      <div>
        <h2 className="text-xl font-semibold text-gray-800">管理后台</h2>
      </div>

      <div className="flex items-center space-x-4">
        <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors">
          <Bell size={20} />
        </button>
        <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors">
          <Settings size={20} />
        </button>
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-medium">
            {user?.username?.charAt(0)?.toUpperCase()}
          </div>
          <span className="text-sm font-medium text-gray-700">{user?.username}</span>
        </div>
      </div>
    </div>
  )
}
