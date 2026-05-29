import ProjectCard from './ProjectCard.jsx'
import { useProjects } from '../../hooks/useProjects.js'

export default function ProjectList() {
  const { projects, loading, error } = useProjects()

  if (loading) {
    return <div className="pl-2 text-xs text-[var(--text-muted)] max-[1024px]:hidden">加载中...</div>
  }

  if (error) {
    return (
      <div className="pl-2 text-xs leading-5 text-red-300 max-[1024px]:hidden">
        项目加载失败：{error}
      </div>
    )
  }

  if (!projects.length) {
    return (
      <div className="pl-2 text-xs leading-5 text-[var(--text-muted)] max-[1024px]:hidden">
        暂无项目
      </div>
    )
  }

  return (
    <div className="space-y-2 pl-2 max-[1024px]:hidden">
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  )
}
