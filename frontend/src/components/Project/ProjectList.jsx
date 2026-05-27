import ProjectCard from './ProjectCard.jsx'
import { useProjects } from '../../hooks/useProjects.js'

export default function ProjectList() {
  const { projects, loading } = useProjects()

  if (loading) {
    return <div className="pl-2 text-xs text-[var(--text-muted)] max-[1024px]:hidden">加载中...</div>
  }

  return (
    <div className="space-y-2 pl-2 max-[1024px]:hidden">
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  )
}
