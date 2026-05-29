import { useState } from 'react'
import { Film, Image, Loader2, Play, RefreshCw, ScrollText } from 'lucide-react'
import { useProjectPolling } from '../../hooks/useProjectPolling.js'
import { useAppStore } from '../../store/appStore.js'
import { regenerateFrame, regenerateFrameImage, retryFrame } from '../../services/frame.js'
import {
  generateProjectScript,
  getGenerationTask,
  getGenerationTaskSteps,
  renderProject,
} from '../../services/project.js'
import VideoPlayer from '../VideoPlayer.jsx'

const STATUS_MAP = {
  0: { text: '待生成', color: 'text-yellow-400' },
  1: { text: '生成中', color: 'text-blue-400' },
  2: { text: '已完成', color: 'text-green-400' },
  3: { text: '失败', color: 'text-red-400' },
}

const SCENE_TYPE_MAP = {
  0: '开场',
  1: '商品展示',
  2: '口播',
  3: '转场',
  4: '结尾',
}

const BUSY_PROJECT_STATUSES = ['script_generating', 'render_queued', 'rendering', 'processing']
const PROJECT_STATUS_TEXT = {
  draft: '待生成',
  script_generating: '剧本生成中',
  script_ready: '剧本就绪',
  review_required: '待确认合成',
  processing: '生成中',
  render_queued: '渲染排队中',
  rendering: '渲染中',
  completed: '已完成',
  failed: '失败',
}

export default function FrameGrid() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const {
    project,
    frames,
    videoUrl,
    loading,
    error,
    refetch,
  } = useProjectPolling(activeProjectId)
  const [regenerating, setRegenerating] = useState({})
  const [flowLoading, setFlowLoading] = useState(null)
  const [task, setTask] = useState(null)
  const [steps, setSteps] = useState([])
  const [flowError, setFlowError] = useState('')

  const refreshTask = async (taskId) => {
    if (!taskId) return
    const [taskData, stepData] = await Promise.all([
      getGenerationTask(taskId),
      getGenerationTaskSteps(taskId),
    ])
    setTask(taskData)
    setSteps(stepData || [])
  }

  const handleGenerateScript = async () => {
    setFlowLoading('script')
    setFlowError('')
    try {
      const result = await generateProjectScript(activeProjectId, { force: frames.length > 0 })
      if (result?.task_id) await refreshTask(result.task_id)
      refetch()
    } catch (err) {
      setFlowError(err.message)
    } finally {
      setFlowLoading(null)
    }
  }

  const handleRenderProject = async () => {
    setFlowLoading('render')
    setFlowError('')
    try {
      const result = await renderProject(activeProjectId)
      if (result?.task_id) await refreshTask(result.task_id)
      refetch()
    } catch (err) {
      setFlowError(err.message)
    } finally {
      setFlowLoading(null)
    }
  }

  const handleRegenerate = async (frameId) => {
    const instruction = prompt('请输入调整指令（可选）')
    if (instruction === null) return
    setRegenerating((prev) => ({ ...prev, [frameId]: 'script' }))
    try {
      await regenerateFrame(activeProjectId, frameId, instruction || undefined)
      refetch()
    } catch (err) {
      alert(`重新生成失败: ${err.message}`)
    } finally {
      setRegenerating((prev) => {
        const next = { ...prev }
        delete next[frameId]
        return next
      })
    }
  }

  const handleRegenerateImage = async (frameId) => {
    const instruction = prompt('请输入图片调整指令（可选）')
    if (instruction === null) return
    setRegenerating((prev) => ({ ...prev, [frameId]: 'image' }))
    try {
      await regenerateFrameImage(activeProjectId, frameId, instruction || undefined)
      refetch()
    } catch (err) {
      alert(`重新生成图片失败: ${err.message}`)
    } finally {
      setRegenerating((prev) => {
        const next = { ...prev }
        delete next[frameId]
        return next
      })
    }
  }

  const handleRetryFrame = async (frameId) => {
    const instruction = prompt('请输入重试要求（可选）')
    if (instruction === null) return
    setRegenerating((prev) => ({ ...prev, [frameId]: 'retry' }))
    try {
      await retryFrame(activeProjectId, frameId, instruction || undefined)
      refetch()
    } catch (err) {
      alert(`重试失败: ${err.message}`)
    } finally {
      setRegenerating((prev) => {
        const next = { ...prev }
        delete next[frameId]
        return next
      })
    }
  }

  if (!activeProjectId) {
    return (
      <div className="flex min-h-screen items-center justify-center px-8 text-sm text-[var(--text-muted)]">
        请选择或新建一个项目
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="animate-spin text-[#7C3AED]" size={32} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-8 text-sm text-red-400">
        {error}
      </div>
    )
  }

  const projectBusy = BUSY_PROJECT_STATUSES.includes(project?.status)
  const scriptBusy = ['script_generating', 'render_queued', 'rendering'].includes(project?.status)
  const canRender = !!frames.length && !projectBusy && !['draft', 'failed'].includes(project?.status)

  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="m-0 text-lg font-semibold">{project?.title || '关键帧管理'}</h1>
          <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
            状态：{PROJECT_STATUS_TEXT[project?.status] || project?.status || '未知'} · {frames.length} 个分镜
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleGenerateScript}
            disabled={!!flowLoading || scriptBusy}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-soft)] px-3 py-2 text-sm text-white hover:bg-[var(--brand-soft)] disabled:opacity-50"
          >
            {flowLoading === 'script' ? <Loader2 size={16} className="animate-spin" /> : <ScrollText size={16} />}
            生成剧本
          </button>
          <button
            type="button"
            onClick={handleRenderProject}
            disabled={!!flowLoading || !canRender}
            className="inline-flex items-center gap-2 rounded-lg bg-[#7C3AED] px-3 py-2 text-sm text-white hover:bg-[#6d28d9] disabled:opacity-50"
          >
            {flowLoading === 'render' ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            开始渲染
          </button>
        </div>
      </header>

      {(flowError || task) && (
        <div className="mb-6 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-4">
          {flowError && <p className="m-0 text-sm text-red-300">{flowError}</p>}
          {task && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-white">任务 {task.id} · {task.current_step || task.status}</span>
                <span className="text-[var(--text-muted)]">{task.progress || 0}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
                <div className="h-full bg-[#7C3AED]" style={{ width: `${task.progress || 0}%` }} />
              </div>
              {!!steps.length && (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {steps.map((step) => (
                    <div key={step.id} className="rounded-md border border-[var(--border-soft)] px-3 py-2 text-xs">
                      <div className="text-white">{step.step_name}</div>
                      <div className="mt-1 text-[var(--text-muted)]">{step.status} · {step.progress || 0}%</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {videoUrl && (
        <div className="mb-6">
          <VideoPlayer src={videoUrl} />
        </div>
      )}

      {!frames.length && (
        <div className="grid min-h-[360px] place-items-center rounded-lg border border-dashed border-[var(--border-soft)] bg-[var(--bg-secondary)] px-6 text-center">
          <div>
            <Film className="mx-auto mb-3 text-[var(--text-muted)]" size={34} />
            <p className="m-0 text-sm text-white">当前项目还没有分镜</p>
            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">先生成剧本，系统会写入基础分镜。</p>
          </div>
        </div>
      )}

      {!!frames.length && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4">
          {frames.map((frame) => {
            const status = STATUS_MAP[frame.status] || STATUS_MAP[0]
            const isRegenerating = regenerating[frame.id]
            return (
              <div
                key={frame.id}
                className="overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[var(--bg-secondary)]"
              >
                <div className="flex aspect-video items-center justify-center bg-[var(--bg-main)]">
                  {frame.image_url ? (
                    <img
                      src={frame.image_url}
                      alt={`分镜 ${frame.sequence}`}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <Image size={32} className="text-[var(--text-muted)]" />
                  )}
                </div>
                <div className="p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">场景 {frame.sequence}</span>
                      {frame.scene_type != null && SCENE_TYPE_MAP[frame.scene_type] && (
                        <span className="rounded-full bg-[rgba(124,58,237,0.2)] px-1.5 py-0.5 text-[10px] text-[#c4b5fd]">
                          {SCENE_TYPE_MAP[frame.scene_type]}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {frame.duration && (
                        <span className="text-xs text-[var(--text-muted)]">{frame.duration}s</span>
                      )}
                      <span className={`text-xs ${status.color}`}>{status.text}</span>
                    </div>
                  </div>
                  <p className="mb-1 line-clamp-2 text-xs text-[var(--text-muted)]">
                    {frame.description || frame.image_prompt || '无描述'}
                  </p>
                  {(frame.text_overlay || frame.subtitle_text) && (
                    <p className="mb-1 line-clamp-1 text-xs text-[#a78bfa]">
                      叠字: {frame.text_overlay || frame.subtitle_text}
                    </p>
                  )}
                  {frame.dirty && (
                    <p className="mb-2 rounded-md bg-yellow-500/10 px-2 py-1 text-xs text-yellow-200">
                      待合成
                    </p>
                  )}
                  {frame.audio_url && (
                    <div className="mb-2">
                      <audio controls src={frame.audio_url} className="h-7 w-full" />
                    </div>
                  )}
                  {frame.status === 3 && frame.error_message && (
                    <p className="mb-2 rounded-lg border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-xs text-red-200">
                      {frame.error_message}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRegenerate(frame.id)}
                      disabled={!!isRegenerating}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[var(--border-soft)] py-1.5 text-xs text-[var(--text-muted)] transition-colors hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50"
                    >
                      <RefreshCw size={12} className={isRegenerating === 'script' ? 'animate-spin' : ''} />
                      重生成
                    </button>
                    <button
                      onClick={() => handleRegenerateImage(frame.id)}
                      disabled={!!isRegenerating}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[var(--border-soft)] py-1.5 text-xs text-[var(--text-muted)] transition-colors hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50"
                    >
                      <Image size={12} className={isRegenerating === 'image' ? 'animate-spin' : ''} />
                      重生成图片
                    </button>
                  </div>
                  {frame.status === 3 && (
                    <button
                      onClick={() => handleRetryFrame(frame.id)}
                      disabled={!!isRegenerating}
                      className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-red-500/40 px-2 py-1.5 text-xs text-red-200 hover:bg-red-500/10 disabled:opacity-50"
                    >
                      <RefreshCw size={12} className={isRegenerating === 'retry' ? 'animate-spin' : ''} />
                      重试失败分镜
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
