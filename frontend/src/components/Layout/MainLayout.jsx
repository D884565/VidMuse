import { useEffect, lazy, Suspense } from 'react'
import ChatContainer from '../Chat/ChatContainer.jsx'
import FrameGrid from '../Keyframes/FrameGrid.jsx'
import MediaGrid from '../Media/MediaGrid.jsx'
import UserProfile from '../User/UserProfile.jsx'
import Sidebar from './Sidebar.jsx'
import { useAppStore } from '../../store/appStore.js'
import { getUserInfo } from '../../services/user.js'
import Login from '../../pages/Login.jsx'

// 后台管理页面 - 懒加载
const AdminDashboard = lazy(() => import('../../pages/admin/Dashboard.jsx'))
const AdminTraceList = lazy(() => import('../../pages/admin/TraceList.jsx'))
const AdminTraceDetail = lazy(() => import('../../pages/admin/TraceDetail.jsx'))

export default function MainLayout() {
  const activeView = useAppStore((state) => state.activeView)
  const isLoggedIn = useAppStore((state) => state.isLoggedIn)
  const authLoading = useAppStore((state) => state.authLoading)
  const user = useAppStore((state) => state.user)
  const setUser = useAppStore((state) => state.setUser)
  const setAuthLoading = useAppStore((state) => state.setAuthLoading)
  const isAdmin = useAppStore(state => state.isAdmin())

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
    // 管理员页面权限校验
    if (activeView.startsWith('admin-') && !isAdmin) {
      return (
        <div className="grid min-h-[60vh] place-items-center">
          <div className="text-center">
            <h3 className="text-lg font-medium mb-2">权限不足</h3>
            <p className="text-[var(--text-muted)] text-sm">您没有访问管理后台的权限</p>
          </div>
        </div>
      )
    }

    // 懒加载组件加载时的fallback
    const SuspenseWrapper = ({ children }) => (
      <Suspense fallback={
        <div className="grid min-h-[60vh] place-items-center">
          <div className="text-[var(--text-muted)]">加载中...</div>
        </div>
      }>
        {children}
      </Suspense>
    )

    switch (activeView) {
      case 'keyframes':
        return <FrameGrid />
      case 'media':
        return <MediaGrid />
      case 'profile':
        return <UserProfile />
      case 'admin-dashboard':
        return <SuspenseWrapper><AdminDashboard /></SuspenseWrapper>
      case 'admin-trace-list':
        return <SuspenseWrapper><AdminTraceList /></SuspenseWrapper>
      case 'admin-trace-detail':
        return <SuspenseWrapper><AdminTraceDetail /></SuspenseWrapper>
      default:
        return <ChatContainer />
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
