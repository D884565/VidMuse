import { useState } from 'react'
import {
  FolderKanban,
  Images,
  KeyRound,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Sparkles,
  User,
} from 'lucide-react'
import ProjectList from '../Project/ProjectList.jsx'
import CreateProjectModal from '../Project/CreateProjectModal.jsx'
import UserProfileMini from './UserProfile.jsx'
import { useAppStore } from '../../store/appStore.js'
import { logoutApi } from '../../services/user.js'

export default function Sidebar() {
  const activeView = useAppStore((state) => state.activeView)
  const setActiveView = useAppStore((state) => state.setActiveView)
  const collapsed = useAppStore((state) => state.sidebarCollapsed)
  const toggleSidebar = useAppStore((state) => state.toggleSidebar)

  const storeLogout = useAppStore((state) => state.logout)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const handleLogout = async () => {
    try { await logoutApi() } catch { /* 忽略退出接口错误，本地仍清理登录态。 */ }
    storeLogout()
  }

  return (
    <>
    <aside
      className={`fixed inset-y-0 left-0 z-20 flex flex-col border-r border-[var(--border-soft)] bg-[var(--bg-sidebar)] transition-all duration-300 ${
        collapsed ? 'w-[72px]' : 'w-[260px]'
      } max-[1024px]:w-[72px]`}
    >
      <div className="flex h-16 items-center gap-3 px-4">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] shadow-[0_4px_24px_rgba(124,58,237,0.25)]">
          <Sparkles size={20} />
        </div>
        <div className={`${collapsed ? 'hidden' : 'block'} max-[1024px]:hidden`}>
          <p className="m-0 text-base font-semibold">VidMuse</p>
          <p className="m-0 text-xs text-[var(--text-muted)]">AI 视频创作台</p>
        </div>
        <button
          aria-label="切换侧边栏"
          className="ml-auto rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white max-[1024px]:hidden"
          type="button"
          onClick={toggleSidebar}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      <nav className="flex-1 space-y-2 px-3 py-4">
        <button
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${
            activeView === 'chat'
              ? 'bg-[var(--brand-soft)] text-white'
              : 'text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white'
          }`}
          type="button"
          onClick={() => setActiveView('chat')}
        >
          <FolderKanban size={18} />
          <span className={`${collapsed ? 'hidden' : 'inline'} max-[1024px]:hidden`}>
            项目
          </span>
        </button>

        {!collapsed && <ProjectList />}

        <button
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${
            activeView === 'media'
              ? 'bg-[var(--brand-soft)] text-white'
              : 'text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white'
          }`}
          type="button"
          onClick={() => setActiveView('media')}
        >
          <Images size={18} />
          <span className="max-[1024px]:hidden">素材库</span>
          <span className="ml-auto rounded-full bg-[rgba(124,58,237,0.22)] px-2 py-0.5 text-xs text-white max-[1024px]:hidden">
            12
          </span>
        </button>

        <button
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${
            activeView === 'keyframes'
              ? 'bg-[var(--brand-soft)] text-white'
              : 'text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white'
          }`}
          type="button"
          onClick={() => setActiveView('keyframes')}
        >
          <KeyRound size={18} />
          <span className="max-[1024px]:hidden">关键帧</span>
        </button>

        <button
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${
            activeView === 'profile'
              ? 'bg-[var(--brand-soft)] text-white'
              : 'text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white'
          }`}
          type="button"
          onClick={() => setActiveView('profile')}
        >
          <User size={18} />
          <span className="max-[1024px]:hidden">个人信息</span>
        </button>

        <div className="my-4 h-px bg-[var(--border-soft)]" />

        <button
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-3 py-2.5 text-sm font-medium shadow-[0_4px_24px_rgba(124,58,237,0.15)] hover:shadow-[0_4px_30px_rgba(124,58,237,0.35)]"
          type="button"
          onClick={() => setShowCreateModal(true)}
        >
          <Plus size={18} />
          <span className={`${collapsed ? 'hidden' : 'inline'} max-[1024px]:hidden`}>
            新建项目
          </span>
        </button>
      </nav>

      <div className="border-t border-[var(--border-soft)] p-3">
        <UserProfileMini collapsed={collapsed} />
        <button
          onClick={handleLogout}
          className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-[var(--text-muted)] hover:bg-red-500/10 hover:text-red-400"
          type="button"
        >
          <LogOut size={18} />
          <span className={`${collapsed ? 'hidden' : 'inline'} max-[1024px]:hidden`}>
            退出登录
          </span>
        </button>
      </div>
    </aside>

      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
      />
    </>
  )
}
