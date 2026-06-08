import { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { getProjects, deleteProject } from '../../services/project.js'
import ConfirmDialog from '../Common/ConfirmDialog.jsx'
import ProjectDetail from './ProjectDetail.jsx'

function appendVideoCacheBuster(url, taskId) {
  if (!url) return url
  const separator = url.includes('?') ? '&' : '?'
  const token = taskId || Date.now()
  return `${url}${separator}v=${encodeURIComponent(token)}`
}

export default function ProjectManager() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedProject, setSelectedProject] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  function fetchProjects() {
    setLoading(true)
    getProjects({ page_size: 100 })
      .then((data) => {
        setProjects(data.list || data.projects || data.items || [])
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteProject(deleteTarget.id)
      setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id))
      if (selectedProject?.id === deleteTarget.id) {
        setSelectedProject(null)
      }
    } catch {
      // 静默处理
    } finally {
      setDeleting(false)
      setDeleteTarget(null)
    }
  }

  const completedProjects = projects.filter(
    (p) => p.workflow_stage === 'completed' || p.video_output_url
  )

  const otherProjects = projects.filter(
    (p) => p.workflow_stage !== 'completed' && !p.video_output_url
  )

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-[var(--text-muted)]">
        加载中...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-red-400">
        加载失败: {error}
      </div>
    )
  }

  return (
    <div className="h-screen overflow-y-auto p-6">
      <h1 className="m-0 mb-6 text-xl font-semibold">项目管理</h1>

      {completedProjects.length > 0 && (
        <section className="mb-8">
          <h2 className="m-0 mb-4 text-sm font-medium text-[var(--text-muted)]">
            已完成项目 ({completedProjects.length})
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {completedProjects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onClick={() => setSelectedProject(project)}
                onDelete={() => setDeleteTarget(project)}
              />
            ))}
          </div>
        </section>
      )}

      {otherProjects.length > 0 && (
        <section>
          <h2 className="m-0 mb-4 text-sm font-medium text-[var(--text-muted)]">
            进行中 ({otherProjects.length})
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {otherProjects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onClick={() => setSelectedProject(project)}
                onDelete={() => setDeleteTarget(project)}
              />
            ))}
          </div>
        </section>
      )}

      {projects.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)]">
          <p className="text-sm">暂无项目</p>
        </div>
      )}

      {selectedProject && (
        <ProjectDetail
          project={selectedProject}
          onClose={() => setSelectedProject(null)}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="删除项目"
        message={`你确定要删除「${deleteTarget?.title || '未命名项目'}」吗？对应的项目内容也会被删除。此操作无法撤销。`}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
      />
    </div>
  )
}

function ProjectCard({ project, onClick, onDelete }) {
  const stage = project.workflow_stage
  const statusText =
    stage === 'completed' ? '已完成' :
    stage === 'video' ? '视频阶段' :
    stage === 'image' ? '图片阶段' :
    stage === 'script' ? '剧本阶段' : '创建中'

  const statusColor =
    stage === 'completed' ? 'bg-[rgba(16,185,129,0.14)] text-[#6ee7b7]' :
    'bg-[rgba(124,58,237,0.14)] text-[#c4b5fd]'
  const displayVideoUrl = appendVideoCacheBuster(project.video_output_url, project.last_task_id)

  return (
    <div className="group relative">
      <button
        className="w-full overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[rgba(26,26,46,0.6)] text-left transition-all hover:-translate-y-0.5 hover:border-[rgba(124,58,237,0.4)] hover:shadow-[0_8px_30px_rgba(124,58,237,0.12)]"
        type="button"
        onClick={onClick}
      >
        {/* 缩略图区域 */}
        <div className="relative aspect-video overflow-hidden bg-[rgba(15,15,30,0.8)]">
          {project.video_output_url ? (
            <video
              key={displayVideoUrl}
              src={displayVideoUrl}
              className="h-full w-full object-cover"
              muted
              preload="metadata"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-[var(--text-muted)]">
              <span className="text-3xl">🎬</span>
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          <span className={`absolute right-2 top-2 rounded-full px-2 py-0.5 text-[11px] ${statusColor}`}>
            {statusText}
          </span>
        </div>

        {/* 信息区域 */}
        <div className="p-3">
          <p className="m-0 truncate text-sm font-medium text-white">{project.title}</p>
          <p className="m-0 mt-1 text-xs text-[var(--text-muted)] line-clamp-1">
            {project.summary || new Date(project.created_at).toLocaleDateString('zh-CN')}
          </p>
        </div>
      </button>

      {/* 删除按钮，hover 时显示 */}
      <button
        type="button"
        className="absolute right-2 top-2 z-10 hidden rounded-lg bg-black/40 p-1.5 text-[var(--text-muted)] backdrop-blur-sm transition hover:bg-red-500/20 hover:text-red-400 group-hover:block"
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
