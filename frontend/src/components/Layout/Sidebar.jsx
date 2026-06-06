import { useEffect, useRef, useState } from 'react'
import {
  ChevronUp,
  FolderKanban,
  Images,
  Plus,
  LogOut,
  MessageSquarePlus,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Film,
  Settings,
  Sparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import ProjectList from '../Project/ProjectList.jsx'
import UserProfileMini from './UserProfile.jsx'
import { useAppStore } from '../../store/appStore.js'
import { logoutApi } from '../../services/user.js'

export default function Sidebar() {
  const activeView = useAppStore((state) => state.activeView)
  const setActiveView = useAppStore((state) => state.setActiveView)
  const collapsed = useAppStore((state) => state.sidebarCollapsed)
  const toggleSidebar = useAppStore((state) => state.toggleSidebar)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const clearDraftConversation = useAppStore((state) => state.clearDraftConversation)
  const isAdmin = useAppStore((state) => state.isAdmin())
  const storeLogout = useAppStore((state) => state.logout)

  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const profileMenuRef = useRef(null)

  useEffect(() => {
    if (!profileMenuOpen) {
      return undefined
    }

    function handlePointerDown(event) {
      if (!profileMenuRef.current?.contains(event.target)) {
        setProfileMenuOpen(false)
      }
    }

    function handleEscape(event) {
      if (event.key === 'Escape') {
        setProfileMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [profileMenuOpen])

  const handleLogout = async () => {
    try {
      await logoutApi()
    } catch {
      // Ignore logout API errors and still clear the local session.
    }
    storeLogout()
  }

  return (
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
          <p className="m-0 text-xs text-[var(--text-muted)]">带货视频生成系统</p>
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
            对话
          </span>
        </button>

        <button
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-3 py-2.5 text-sm font-medium shadow-[0_4px_24px_rgba(124,58,237,0.15)] hover:shadow-[0_4px_30px_rgba(124,58,237,0.35)]"
          type="button"
          onClick={() => {
            setActiveProjectId(null)
            clearDraftConversation()
            setActiveView('chat')
          }}
        >
          <MessageSquarePlus size={18} />
          <span className={`${collapsed ? 'hidden' : 'inline'} max-[1024px]:hidden`}>
            新建对话
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
        </button>

        <button
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${
            activeView === 'products'
              ? 'bg-[var(--brand-soft)] text-white'
              : 'text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white'
          }`}
          type="button"
          onClick={() => setActiveView('products')}
        >
          <Package size={18} />
          <span className="max-[1024px]:hidden">商品</span>
        </button>

        <button
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${
            activeView === 'projects'
              ? 'bg-[var(--brand-soft)] text-white'
              : 'text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white'
          }`}
          type="button"
          onClick={() => setActiveView('projects')}
        >
          <Film size={18} />
          <span className="max-[1024px]:hidden">项目管理</span>
        </button>

        {isAdmin && (
          <Link
            to="/admin/dashboard"
            target="_blank"
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white"
          >
            <Settings size={18} />
            <span className="max-[1024px]:hidden">管理后台</span>
          </Link>
        )}
      </nav>

      <div className="border-t border-[var(--border-soft)] p-3">
        <div className="relative" ref={profileMenuRef}>
          <button
            className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-[rgba(255,255,255,0.05)]"
            type="button"
            onClick={() => setProfileMenuOpen((open) => !open)}
          >
            <UserProfileMini collapsed={collapsed} />
            <ChevronUp
              size={16}
              className={`${collapsed ? 'hidden' : 'ml-auto'} max-[1024px]:hidden ${
                profileMenuOpen ? 'rotate-180' : ''
              } transition-transform`}
            />
          </button>

          {profileMenuOpen && (
            <div className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-2xl border border-[var(--border-soft)] bg-[rgba(18,18,26,0.96)] p-2 shadow-[0_20px_50px_rgba(0,0,0,0.35)]">
              <button
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-[var(--text-muted)] transition hover:bg-[var(--brand-soft)] hover:text-white"
                type="button"
                onClick={() => {
                  setActiveView('profile')
                  setProfileMenuOpen(false)
                }}
              >
                <span className="grid h-8 w-8 place-items-center rounded-full bg-[rgba(124,58,237,0.18)] text-xs font-semibold text-white">
                  资料
                </span>
                <span>个人信息</span>
              </button>

              <button
                className="mt-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-red-400 transition hover:bg-red-500/10"
                type="button"
                onClick={handleLogout}
              >
                <span className="grid h-8 w-8 place-items-center rounded-full bg-red-500/10">
                  <LogOut size={15} />
                </span>
                <span>退出登录</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
