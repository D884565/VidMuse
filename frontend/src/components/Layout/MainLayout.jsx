import { useEffect } from 'react'
import WorkbenchView from '../Workbench/WorkbenchView.jsx'
import FrameGrid from '../Keyframes/FrameGrid.jsx'
import MediaGrid from '../Media/MediaGrid.jsx'
import UserProfile from '../User/UserProfile.jsx'
import ProjectManager from '../Project/ProjectManager.jsx'
import Sidebar from './Sidebar.jsx'
import { useAppStore } from '../../store/appStore.js'
import { getUserInfo } from '../../services/user.js'
import Login from '../../pages/Login.jsx'

export default function MainLayout() {
  const activeView = useAppStore((state) => state.activeView)
  const isLoggedIn = useAppStore((state) => state.isLoggedIn)
  const authLoading = useAppStore((state) => state.authLoading)
  const user = useAppStore((state) => state.user)
  const setUser = useAppStore((state) => state.setUser)
  const setAuthLoading = useAppStore((state) => state.setAuthLoading)

  // 页面刷新后恢复用户信息
  useEffect(() => {
    if (isLoggedIn && !user) {
      setAuthLoading(true)
      getUserInfo()
        .then((data) => setUser({ id: data.id, username: data.username, role: data.role }))
        .catch(() => {
          // token 已失效，清除登录状态
          useAppStore.getState().logout()
        })
        .finally(() => setAuthLoading(false))
    } else {
      setAuthLoading(false)
    }
  }, [isLoggedIn, user, setUser, setAuthLoading])

  if (authLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--bg-main)] text-sm text-[var(--text-muted)]">
        正在恢复登录状态...
      </div>
    )
  }

  // 未登录时显示登录页
  if (!isLoggedIn) {
    return <Login />
  }

  const renderView = () => {
    switch (activeView) {
      case 'keyframes':
        return <FrameGrid />
      case 'media':
        return <MediaGrid />
      case 'profile':
        return <UserProfile />
      case 'projects':
        return <ProjectManager />
      default:
        return <WorkbenchView />
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-white">
      <Sidebar />
      <main className="ml-[260px] min-h-screen transition-[margin] duration-300 max-[1024px]:ml-[72px]">
        {renderView()}
      </main>
    </div>
  )
}
