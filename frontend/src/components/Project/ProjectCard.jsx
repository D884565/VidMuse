import { useAppStore } from '../../store/appStore.js'

export default function ProjectCard({ project }) {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const active = activeProjectId === project.id

  return (
    <button
      className={`w-full rounded-lg border px-3 py-2 text-left transition hover:-translate-y-0.5 ${
        active
          ? 'border-[rgba(124,58,237,0.45)] bg-[rgba(124,58,237,0.13)]'
          : 'border-transparent bg-transparent hover:border-[var(--border-soft)] hover:bg-[rgba(255,255,255,0.03)]'
      }`}
      type="button"
      onClick={() => setActiveProjectId(project.id)}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm text-white">{project.name}</span>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${
            project.status === '生成中'
              ? 'bg-[rgba(124,58,237,0.22)] text-[#c4b5fd]'
              : 'bg-[rgba(16,185,129,0.14)] text-[#6ee7b7]'
          }`}
        >
          {project.status}
        </span>
      </div>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        {project.createdAt} · {project.videos} 个视频
      </p>
    </button>
  )
}
