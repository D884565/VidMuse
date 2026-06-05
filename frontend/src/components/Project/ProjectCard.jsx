import { useAppStore } from '../../store/appStore.js'

// 后端状态映射
const STATUS_DISPLAY = {
  0: { text: '待生成', color: 'bg-[rgba(234,179,8,0.14)] text-[#fbbf24]' },
  1: { text: '剧本就绪', color: 'bg-[rgba(168,85,247,0.14)] text-[#c4b5fd]' },
  2: { text: '生成中', color: 'bg-[rgba(124,58,237,0.22)] text-[#c4b5fd]' },
  3: { text: '已完成', color: 'bg-[rgba(16,185,129,0.14)] text-[#6ee7b7]' },
  4: { text: '失败', color: 'bg-[rgba(239,68,68,0.14)] text-[#f87171]' },
}

export default function ProjectCard({ project }) {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const setActiveView = useAppStore((state) => state.setActiveView)
  const active = activeProjectId === project.id

  const status = STATUS_DISPLAY[project.status] || STATUS_DISPLAY[0]
  const frameCount = project.frame_count ?? 0
  const createdDate = project.created_at
    ? new Date(project.created_at).toLocaleDateString('zh-CN')
    : ''

  return (
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
        <span className="truncate text-sm text-white">{project.title}</span>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${status.color}`}>
          {project.status_name || status.text}
        </span>
      </div>
      <p className="mt-1 text-xs text-[var(--text-muted)] line-clamp-1">
        {project.summary || `${createdDate} · ${frameCount} 个帧`}
      </p>
    </button>
  )
}
