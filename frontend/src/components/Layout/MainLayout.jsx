import ChatContainer from '../Chat/ChatContainer.jsx'
import KeyframeStudio from '../Keyframes/KeyframeStudio.jsx'
import MediaGrid from '../Media/MediaGrid.jsx'
import Sidebar from './Sidebar.jsx'
import { useAppStore } from '../../store/appStore.js'

export default function MainLayout() {
  const activeView = useAppStore((state) => state.activeView)

  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-white">
      <Sidebar />
      <main className="ml-[260px] min-h-screen transition-[margin] duration-300 max-[1024px]:ml-[72px]">
        {activeView === 'keyframes' ? (
          <KeyframeStudio />
        ) : activeView === 'media' ? (
          <MediaGrid />
        ) : (
          <ChatContainer />
        )}
      </main>
    </div>
  )
}
