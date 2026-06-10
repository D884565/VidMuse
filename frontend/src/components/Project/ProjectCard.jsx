import { useRef, useState } from 'react'
import { MoreHorizontal, Trash2 } from 'lucide-react'
import { deleteProject } from '../../services/project.js'
import { useAppStore } from '../../store/appStore.js'
import ConfirmDialog from '../Common/ConfirmDialog.jsx'

// 后端状态映射
const STATUS_DISPLAY = {
  0: { text: '待生成', color: 'bg-[rgba(234,179,8,0.14)] text-[#fbbf24]' },
  1: { text: '剧本就绪', color: 'bg-[rgba(168,85,247,0.14)] text-[#c4b5fd]' },
  2: { text: '生成中', color: 'bg-[rgba(124,58,237,0.22)] text-[#c4b5fd]' },
  3: { text: '已完成', color: 'bg-[rgba(16,185,129,0.14)] text-[#6ee7b7]' },
  4: { text: '失败', color: 'bg-[rgba(239,68,68,0.14)] text-[#f87171]' },
}

function getWorkflowStatusDisplay(project) {
  const fallback = STATUS_DISPLAY[project.status] || STATUS_DISPLAY[0]
  const stage = project.workflow_stage
  const stageStatus = project.stage_status

  if (stage === 'completed') {
    return { text: project.status_name || '已完成', color: STATUS_DISPLAY[3].color }
  }
  if (stageStatus === 'failed') {
    return { text: project.status_name || '失败', color: STATUS_DISPLAY[4].color }
  }
  if (stageStatus === 'running') {
    return {
      text: project.status_name || {
        script: '剧本生成中',
        image: '图片生成中',
        video: '视频生成中',
      }[stage] || '生成中',
      color: STATUS_DISPLAY[2].color,
    }
  }
  if (stageStatus === 'awaiting_review') {
    return {
      text: project.status_name || {
        script: '剧本就绪',
        image: '图片待确认',
        video: '视频待确认',
      }[stage] || '待确认',
      color: 'bg-[rgba(168,85,247,0.14)] text-[#c4b5fd]',
    }
  }
  if (stageStatus === 'confirmed') {
    return {
      text: project.status_name || {
        script: '剧本已确认',
        image: '图片已确认',
        video: '视频已确认',
      }[stage] || '已确认',
      color: 'bg-[rgba(59,130,246,0.14)] text-[#93c5fd]',
    }
  }
  return { text: project.status_name || fallback.text, color: fallback.color }
}

function getSidebarProjectTitle(project) {
  const title = (project.title || '').trim()
  if (!title) return '未命名视频项目'
  if (title.endsWith('带货视频生成')) return title
  if (title.endsWith('带货视频')) return `${title}生成`
  return title
}

export default function ProjectCard({ project }) {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const setActiveView = useAppStore((state) => state.setActiveView)
  const clearDraftConversation = useAppStore((state) => state.clearDraftConversation)
  const bumpProjectListVersion = useAppStore((state) => state.bumpProjectListVersion)
  const active = activeProjectId === project.id

  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const triggerRef = useRef(null)

  const status = getWorkflowStatusDisplay(project)
  const sidebarTitle = getSidebarProjectTitle(project)
  const frameCount = project.frame_count ?? 0
  const createdDate = project.created_at
    ? new Date(project.created_at).toLocaleDateString('zh-CN')
    : ''

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteProject(project.id)
      if (activeProjectId === project.id) {
        setActiveProjectId(null)
        clearDraftConversation()
      }
      bumpProjectListVersion()
    } catch {
      // 静默失败，列表会自动刷新
    } finally {
      setDeleting(false)
      setConfirmOpen(false)
    }
  }

  return (
    <div className="group relative">
      <button
        className={`w-full rounded-lg border px-3 py-2 text-left transition hover:-translate-y-0.5 ${
          active
            ? 'border-[rgba(124,58,237,0.45)] bg-[rgba(124,58,237,0.13)]'
            : 'border-transparent bg-transparent hover:border-[var(--border-soft)] hover:bg-[rgba(255,255,255,0.03)]'
        }`}
        type="button"
        onClick={() => {
          setActiveProjectId(project.id)
          setActiveView('chat')
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm text-white">{sidebarTitle}</span>
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${status.color}`}>
            {status.text}
          </span>
        </div>
        <p className="mt-1 text-xs text-[var(--text-muted)] line-clamp-1">
          {project.summary || `${createdDate} · ${frameCount} 个帧`}
        </p>
      </button>

      {/* "..." 按钮，hover 时显示 */}
      <button
        ref={triggerRef}
        type="button"
        className="absolute right-1 top-1/2 -translate-y-1/2 hidden rounded-md p-1 text-[var(--text-muted)] transition hover:bg-[rgba(255,255,255,0.08)] hover:text-white group-hover:block"
        onClick={(e) => {
          e.stopPropagation()
          setMenuOpen((v) => !v)
        }}
      >
        <MoreHorizontal size={14} />
      </button>

      {/* 下拉菜单：用 fixed 定位，避免被 overflow-y-auto 裁剪 */}
      {menuOpen && (() => {
        const rect = triggerRef.current?.getBoundingClientRect()
        const top = rect ? rect.bottom + 4 : 0
        const right = rect ? window.innerWidth - rect.right : 0
        return (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
            <div
              className="fixed z-50 w-32 overflow-hidden rounded-lg border border-[var(--border-soft)] bg-[rgba(26,26,46,0.95)] py-1 shadow-xl"
              style={{ top: `${top}px`, right: `${right}px` }}
            >
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-red-400 transition hover:bg-red-500/10"
                onClick={(e) => {
                  e.stopPropagation()
                  setMenuOpen(false)
                  setConfirmOpen(true)
                }}
              >
                <Trash2 size={12} />
                删除项目
              </button>
            </div>
          </>
        )
      })()}

      <ConfirmDialog
        open={confirmOpen}
        title="删除项目"
        message={`你确定要删除「${sidebarTitle}」吗？对应的项目内容也会被删除。此操作无法撤销。`}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleDelete}
      />
    </div>
  )
}
