import { useEffect } from 'react'
import WorkbenchView from '../Workbench/WorkbenchView.jsx'
import FrameGrid from '../Keyframes/FrameGrid.jsx'
import MediaGrid from '../Media/MediaGrid.jsx'
import ProductManager from '../Product/ProductManager.jsx'
import UserProfile from '../User/UserProfile.jsx'
import ProjectManager from '../Project/ProjectManager.jsx'
import Sidebar from './Sidebar.jsx'
import { useAppStore } from '../../store/appStore.js'
import { getUserInfo } from '../../services/user.js'
import { restoreSession } from '../../services/sessionRestore.js'
import Login from '../../pages/Login.jsx'

/** 登录会话恢复超时时间（毫秒） */
const SESSION_RESTORE_TIMEOUT_MS = 8000

/**
 * 主布局组件
 * 负责登录状态校验、会话恢复，以及根据 activeView 路由到对应页面。
 */
export default function MainLayout() {
  const activeView = useAppStore((state) => state.activeView)
  const isLoggedIn = useAppStore((state) => state.isLoggedIn)
  const authLoading = useAppStore((state) => state.authLoading)
  const user = useAppStore((state) => state.user)
  const setUser = useAppStore((state) => state.setUser)
  const setAuthLoading = useAppStore((state) => state.setAuthLoading)

  useEffect(() => {
    let cancelled = false

    if (isLoggedIn && !user) {
      setAuthLoading(true)

      restoreSession(getUserInfo, { timeoutMs: SESSION_RESTORE_TIMEOUT_MS })
        .then((currentUser) => {
          if (!cancelled) {
            setUser(currentUser)
          }
        })
        .catch(() => {
          if (!cancelled) {
            useAppStore.getState().logout()
          }
        })
        .finally(() => {
          if (!cancelled) {
            setAuthLoading(false)
          }
        })

      return () => {
        cancelled = true
      }
    }

    setAuthLoading(false)

    return () => {
      cancelled = true
    }
  }, [isLoggedIn, user, setUser, setAuthLoading])

  if (authLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--bg-main)] text-sm text-[var(--text-muted)]">
        正在恢复登录状态...
      </div>
    )
  }

  if (!isLoggedIn) {
    return <Login />
  }

  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-white">
      <Sidebar />
      <main className="ml-[260px] min-h-screen transition-[margin] duration-300 max-[1024px]:ml-[72px]">
        {activeView === 'keyframes' && <FrameGrid />}
        {activeView === 'media' && <MediaGrid />}
        {activeView === 'products' && <ProductManager />}
        {activeView === 'profile' && <UserProfile />}
        {activeView === 'projects' && <ProjectManager />}
        {!['keyframes', 'media', 'products', 'profile', 'projects'].includes(activeView) && <WorkbenchView />}
      </main>
    </div>
  )
}
