import ProjectCard from './ProjectCard.jsx'
import { useProjects } from '../../hooks/useProjects.js'
import { useAppStore } from '../../store/appStore.js'

export default function ProjectList() {
  const { projects, loading, error } = useProjects()
  const draftConversationTitle = useAppStore((state) => state.draftConversationTitle)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const setActiveView = useAppStore((state) => state.setActiveView)

  const draftItem = draftConversationTitle ? (
    <button
      className="w-full rounded-lg border border-[rgba(124,58,237,0.45)] bg-[rgba(124,58,237,0.13)] px-3 py-2 text-left transition hover:-translate-y-0.5"
      type="button"
      onClick={() => {
        setActiveProjectId(null)
        setActiveView('chat')
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm text-white">{draftConversationTitle}</span>
      </div>
      <p className="mt-1 text-xs text-[var(--text-muted)] line-clamp-1">普通对话，未创建项目</p>
    </button>
  ) : null

  if (loading) {
    return (
      <div className="space-y-2 pl-2 max-[1024px]:hidden">
        {draftItem}
        <div className="text-xs text-[var(--text-muted)]">加载中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-2 pl-2 max-[1024px]:hidden">
        {draftItem}
        <div className="text-xs leading-5 text-red-300">项目加载失败：{error}</div>
      </div>
    )
  }

  if (!projects.length && !draftItem) {
    return (
      <div className="pl-2 text-xs leading-5 text-[var(--text-muted)] max-[1024px]:hidden">
        暂无项目
      </div>
    )
  }

  return (
    <div className="space-y-2 pl-2 max-[1024px]:hidden">
      {draftItem}
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  )
}
