import ProjectCard from './ProjectCard.jsx'
import { useProjects } from '../../hooks/useProjects.js'

export default function ProjectList() {
  const projects = useProjects()

  return (
    <div className="space-y-2 pl-2 max-[1024px]:hidden">
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  )
}
