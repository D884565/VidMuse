import ChatContainer from '../Chat/ChatContainer.jsx'
import FrameGrid from '../Keyframes/FrameGrid.jsx'
import MediaGrid from '../Media/MediaGrid.jsx'
import Sidebar from './Sidebar.jsx'
import { useAppStore } from '../../store/appStore.js'
import Login from '../../pages/Login.jsx'

export default function MainLayout() {
  const activeView = useAppStore((state) => state.activeView)
  const isLoggedIn = useAppStore((state) => state.isLoggedIn)

  // 未登录时显示登录页
  if (!isLoggedIn) {
    return <Login />
  }

  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-white">
      <Sidebar />
      <main className="ml-[260px] min-h-screen transition-[margin] duration-300 max-[1024px]:ml-[72px]">
        {activeView === 'keyframes' ? (
          <FrameGrid />
        ) : activeView === 'media' ? (
          <MediaGrid />
        ) : (
          <ChatContainer />
        )}
      </main>
    </div>
  )
}
