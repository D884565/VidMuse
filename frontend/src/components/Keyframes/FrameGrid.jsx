import { useEffect, useMemo, useState } from 'react'
import {
  Download,
  Edit3,
  Film,
  Image as ImageIcon,
  Loader2,
  Play,
  RefreshCw,
  ScrollText,
  Video,
} from 'lucide-react'
import { useProjectPolling } from '../../hooks/useProjectPolling.js'
import { useAppStore } from '../../store/appStore.js'
import {
  regenerateFrame,
  regenerateFrameImage,
  regenerateFrameVideo,
  retryFrame,
  updateFrame,
} from '../../services/frame.js'
import {
  advanceWorkflowStage,
  downloadProjectVideo,
  generateProjectScript,
  getGenerationTask,
  getGenerationTaskSteps,
} from '../../services/project.js'
import StoryboardTimeline from '../Workflow/StoryboardTimeline.jsx'
import VideoPlayer from '../VideoPlayer.jsx'

const STATUS_MAP = {
  0: { text: '待处理', color: 'text-yellow-300' },
  1: { text: '生成中', color: 'text-blue-300' },
  2: { text: '已完成', color: 'text-green-300' },
  3: { text: '失败', color: 'text-red-300' },
}

/**
 * 从 workflow_stage + stage_status 推导状态文案，不再依赖旧 project.status 字符串。
 */
function getWorkflowStatusText(workflowStage, stageStatus) {
  if (workflowStage === 'completed') return '已完成'
  if (stageStatus === 'failed') return '失败'
  if (stageStatus === 'running') {
    if (workflowStage === 'script') return '正在生成剧本'
    if (workflowStage === 'image') return '正在生成图片'
    if (workflowStage === 'video') return '正在生成视频'
    return '处理中'
  }
  if (stageStatus === 'awaiting_review') {
    if (workflowStage === 'script') return '剧本已就绪'
    if (workflowStage === 'image') return '图片已就绪'
    if (workflowStage === 'video') return '视频已就绪'
    return '待审核'
  }
  if (workflowStage === 'created') return '草稿'
  return '就绪'
}
const TERMINAL_TASK_STATUSES = ['succeeded', 'failed', 'cancelled']

function getTaskIdentifier(task) {
  return task?.id ?? task?.task_id ?? null
}

const DEFAULT_EDIT_FORM = {
  narration: '',
  subtitle_text: '',
  subtitle_position: 'bottom',
  image_prompt: '',
  video_prompt: '',
  duration: 3,
  sequence: 1,
}

function buildEditForm(frame) {
  return {
    narration: frame?.narration || '',
    subtitle_text: frame?.subtitle_text || '',
    subtitle_position: frame?.subtitle_position || 'bottom',
    image_prompt: frame?.image_prompt || '',
    video_prompt: frame?.video_prompt || '',
    duration: Number(frame?.duration || 3),
    sequence: Number(frame?.sequence || 1),
  }
}

function PromptModal({ open, title, description, value, setValue, onClose, onConfirm, loading }) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-lg rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-5 shadow-2xl">
        <h3 className="m-0 text-base font-semibold text-white">{title}</h3>
        {description ? <p className="mt-2 text-sm text-[var(--text-muted)]">{description}</p> : null}
        <textarea
          rows={5}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="可选的指令说明"
          className="mt-4 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-4 py-3 text-sm text-white outline-none focus:border-[#7C3AED]"
        />
        <div className="mt-4 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="flex-1 rounded-xl border border-[var(--border-soft)] px-4 py-2.5 text-sm text-[var(--text-muted)] hover:bg-[var(--brand-soft)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 rounded-xl bg-[#7C3AED] px-4 py-2.5 text-sm text-white hover:bg-[#6d28d9] disabled:opacity-50"
          >
            {loading ? '提交中...' : '确认'}
          </button>
        </div>
      </div>
    </div>
  )
}

function FrameEditModal({ frame, form, setForm, saving, onClose, onSave }) {
  if (!frame) return null

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-3xl rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="m-0 text-lg font-semibold text-white">编辑分镜 {frame.sequence}</h3>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg border border-[var(--border-soft)] px-3 py-1.5 text-sm text-[var(--text-muted)] hover:bg-[var(--brand-soft)]"
          >
            关闭
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm text-[var(--text-muted)]">
            序号
            <input
              type="number"
              value={form.sequence}
              onChange={(event) => updateField('sequence', Number(event.target.value || 1))}
              className="mt-1 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-3 py-2 text-white outline-none focus:border-[#7C3AED]"
            />
          </label>
          <label className="text-sm text-[var(--text-muted)]">
            时长
            <input
              type="number"
              step="0.1"
              value={form.duration}
              onChange={(event) => updateField('duration', Number(event.target.value || 1))}
              className="mt-1 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-3 py-2 text-white outline-none focus:border-[#7C3AED]"
            />
          </label>
          <label className="text-sm text-[var(--text-muted)] md:col-span-2">
            旁白
            <textarea
              rows={3}
              value={form.narration}
              onChange={(event) => updateField('narration', event.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-3 py-2 text-white outline-none focus:border-[#7C3AED]"
            />
          </label>
          <label className="text-sm text-[var(--text-muted)] md:col-span-2">
            字幕文本
            <input
              type="text"
              value={form.subtitle_text}
              onChange={(event) => updateField('subtitle_text', event.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-3 py-2 text-white outline-none focus:border-[#7C3AED]"
            />
          </label>
          <label className="text-sm text-[var(--text-muted)]">
            字幕位置
            <input
              type="text"
              value={form.subtitle_position}
              onChange={(event) => updateField('subtitle_position', event.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-3 py-2 text-white outline-none focus:border-[#7C3AED]"
            />
          </label>
          <div />
          <label className="text-sm text-[var(--text-muted)] md:col-span-2">
            图片提示词
            <textarea
              rows={3}
              value={form.image_prompt}
              onChange={(event) => updateField('image_prompt', event.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-3 py-2 text-white outline-none focus:border-[#7C3AED]"
            />
          </label>
          <label className="text-sm text-[var(--text-muted)] md:col-span-2">
            视频提示词
            <textarea
              rows={3}
              value={form.video_prompt}
              onChange={(event) => updateField('video_prompt', event.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-main)] px-3 py-2 text-white outline-none focus:border-[#7C3AED]"
            />
          </label>
        </div>

        <div className="mt-5 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="flex-1 rounded-xl border border-[var(--border-soft)] px-4 py-2.5 text-sm text-[var(--text-muted)] hover:bg-[var(--brand-soft)] disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="flex-1 rounded-xl bg-[#7C3AED] px-4 py-2.5 text-sm text-white hover:bg-[#6d28d9] disabled:opacity-50"
          >
            {saving ? '保存中...' : '保存并标记需重新确认'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function FrameGrid() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const { project, frames, videoUrl, loading, error, refetch } = useProjectPolling(activeProjectId)
  const [regenerating, setRegenerating] = useState({})
  const [flowLoading, setFlowLoading] = useState(null)
  const [task, setTask] = useState(null)
  const [steps, setSteps] = useState([])
  const [flowError, setFlowError] = useState('')
  const [actionMessage, setActionMessage] = useState('')
  const [promptModal, setPromptModal] = useState({ open: false, mode: null, frameId: null, value: '' })
  const [editingFrame, setEditingFrame] = useState(null)
  const [editForm, setEditForm] = useState(DEFAULT_EDIT_FORM)
  const [savingFrame, setSavingFrame] = useState(false)

  const activePromptFrame = useMemo(
    () => frames.find((frame) => frame.id === promptModal.frameId) || null,
    [frames, promptModal.frameId]
  )

  const refreshTask = async (taskId) => {
    if (!taskId) return
    const [taskData, stepData] = await Promise.all([getGenerationTask(taskId), getGenerationTaskSteps(taskId)])
    setTask(taskData)
    setSteps(stepData || [])
  }

  useEffect(() => {
    const taskId = getTaskIdentifier(task)
    if (!taskId || TERMINAL_TASK_STATUSES.includes(task.status)) return undefined

    const timerId = setInterval(() => {
      refreshTask(taskId).catch(() => {})
    }, 3000)

    return () => clearInterval(timerId)
  }, [task?.id, task?.task_id, task?.status])

  const handleGenerateScript = async () => {
    setFlowLoading('script')
    setFlowError('')
    setActionMessage('')
    try {
      const result = await generateProjectScript(activeProjectId, { force: frames.length > 0 })
      if (result?.task_id) {
        await refreshTask(result.task_id)
      }
      if (result?.message) setActionMessage(result.message)
      refetch()
    } catch (err) {
      setFlowError(err.message)
    } finally {
      setFlowLoading(null)
    }
  }

  const handleGenerateImages = async () => {
    setFlowLoading('image')
    setFlowError('')
    setActionMessage('')
    try {
      const result = await advanceWorkflowStage(activeProjectId, 'script')
      if (result?.task_id) {
        await refreshTask(result.task_id)
      }
      if (result?.message) setActionMessage(result.message)
      refetch()
    } catch (err) {
      setFlowError(err.message)
    } finally {
      setFlowLoading(null)
    }
  }

  const handleGenerateVideo = async () => {
    setFlowLoading('video')
    setFlowError('')
    setActionMessage('')
    try {
      const result = await advanceWorkflowStage(activeProjectId, 'image')
      if (result?.task_id) {
        await refreshTask(result.task_id)
      }
      if (result?.message) setActionMessage(result.message)
      refetch()
    } catch (err) {
      setFlowError(err.message)
    } finally {
      setFlowLoading(null)
    }
  }

  const handleExportProject = async () => {
    setFlowLoading('export')
    setFlowError('')
    setActionMessage('')
    try {
      const result = await downloadProjectVideo(activeProjectId)
      setActionMessage(`Download started: ${result.filename}`)
    } catch (err) {
      setFlowError(err.message)
    } finally {
      setFlowLoading(null)
    }
  }

  const openPrompt = (mode, frameId) => {
    setPromptModal({ open: true, mode, frameId, value: '' })
  }

  const closePrompt = () => {
    setPromptModal({ open: false, mode: null, frameId: null, value: '' })
  }

  const runFrameAction = async (frameId, mode, action) => {
    setRegenerating((prev) => ({ ...prev, [frameId]: mode }))
    setFlowError('')
    setActionMessage('')
    try {
      const result = await action()
      if (result?.task_id) {
        await refreshTask(result.task_id)
      }
      if (result?.message) {
        setActionMessage(result.message)
      }
      refetch()
      closePrompt()
    } catch (err) {
      setFlowError(err.message || '操作失败')
    } finally {
      setRegenerating((prev) => {
        const next = { ...prev }
        delete next[frameId]
        return next
      })
    }
  }

  const handleConfirmPrompt = async () => {
    const frameId = promptModal.frameId
    if (!frameId || !activeProjectId) return

    if (promptModal.mode === 'script') {
      await runFrameAction(frameId, 'script', () =>
        regenerateFrame(activeProjectId, frameId, promptModal.value || undefined)
      )
    }

    if (promptModal.mode === 'image') {
      await runFrameAction(frameId, 'image', () =>
        regenerateFrameImage(activeProjectId, frameId, promptModal.value || undefined)
      )
    }

    if (promptModal.mode === 'video') {
      await runFrameAction(frameId, 'video', () =>
        regenerateFrameVideo(activeProjectId, frameId, promptModal.value || undefined)
      )
    }

    if (promptModal.mode === 'retry') {
      await runFrameAction(frameId, 'retry', () =>
        retryFrame(activeProjectId, frameId, promptModal.value || undefined)
      )
    }
  }

  const handleRegenerate = (frameId) => openPrompt('script', frameId)
  const handleRegenerateImage = (frameId) => openPrompt('image', frameId)
  const handleRegenerateVideo = (frameId) => openPrompt('video', frameId)
  const handleRetryFrame = (frameId) => openPrompt('retry', frameId)

  const openEditFrame = (frame) => {
    setEditingFrame(frame)
    setEditForm(buildEditForm(frame))
  }

  const closeEditFrame = () => {
    setEditingFrame(null)
    setEditForm(DEFAULT_EDIT_FORM)
  }

  const handleSaveFrameEdit = async () => {
    if (!editingFrame || !activeProjectId) return
    setSavingFrame(true)
    setFlowError('')
    setActionMessage('')
    try {
      const result = await updateFrame(activeProjectId, editingFrame.id, editForm)
      if (result?.message) {
        setActionMessage(result.message)
      } else {
        setActionMessage('分镜已保存，请重新确认后续工作流。')
      }
      refetch()
      closeEditFrame()
    } catch (err) {
      setFlowError(err.message || '保存失败')
    } finally {
      setSavingFrame(false)
    }
  }

  if (!activeProjectId) {
    return (
      <div className="flex min-h-screen items-center justify-center px-8 text-sm text-[var(--text-muted)]">
        请先选择或创建一个项目。
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

  const workflowRunning = project?.stage_status === 'running'
  const videoWorkflowRunning = project?.workflow_stage === 'video' && workflowRunning
  const scriptWorkflowRunning = project?.workflow_stage === 'script' && workflowRunning
  const projectBusy = workflowRunning
  const scriptBusy = scriptWorkflowRunning || videoWorkflowRunning
  const canGenerateImages = !!frames.length && !projectBusy && project?.workflow_stage === 'script'
  const canGenerateVideo = !!frames.length && !projectBusy && project?.workflow_stage === 'image'

  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="m-0 text-lg font-semibold">{project?.title || '分镜工作台'}</h1>
          <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
            状态: {getWorkflowStatusText(project?.workflow_stage, project?.stage_status)} · {frames.length} 个分镜
          </p>
          {task?.status ? (
            <p className="m-0 mt-1 text-xs text-[#a78bfa]">
              最新任务: {task.status} · {task.current_step || '未知'}
            </p>
          ) : null}
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
            onClick={handleGenerateImages}
            disabled={!!flowLoading || !canGenerateImages}
            className="inline-flex items-center gap-2 rounded-lg bg-[#7C3AED] px-3 py-2 text-sm text-white hover:bg-[#6d28d9] disabled:opacity-50"
          >
            {flowLoading === 'image' ? <Loader2 size={16} className="animate-spin" /> : <ImageIcon size={16} />}
            生成图片
          </button>
          <button
            type="button"
            onClick={handleGenerateVideo}
            disabled={!!flowLoading || !canGenerateVideo}
            className="inline-flex items-center gap-2 rounded-lg bg-[#7C3AED] px-3 py-2 text-sm text-white hover:bg-[#6d28d9] disabled:opacity-50"
          >
            {flowLoading === 'video' ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            生成视频
          </button>
          <button
            type="button"
            onClick={handleExportProject}
            disabled={!!flowLoading || !videoUrl}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-soft)] px-3 py-2 text-sm text-white hover:bg-[var(--brand-soft)] disabled:opacity-50"
          >
            {flowLoading === 'export' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
            导出
          </button>
        </div>
      </header>

      {(flowError || actionMessage || task) && (
        <div className="mb-6 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-4">
          {flowError ? <p className="m-0 text-sm text-red-300">{flowError}</p> : null}
          {actionMessage ? <p className="m-0 text-sm text-[#c4b5fd]">{actionMessage}</p> : null}
          {task ? (
            <div className="mt-3 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-white">
                  任务 {getTaskIdentifier(task)} · {task.status} · {task.current_step || '未知'}
                </span>
                <span className="text-[var(--text-muted)]">{task.progress || 0}%</span>
              </div>
              {task.current_step === 'RETRYING' ? (
                <p className="m-0 rounded-md border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-100">
                  任务重试中，项目状态可能仍显示为运行中。
                </p>
              ) : null}
              <div className="h-2 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
                <div className="h-full bg-[#7C3AED]" style={{ width: `${task.progress || 0}%` }} />
              </div>
              {steps.length ? (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {steps.map((step) => (
                    <div key={step.id} className="rounded-md border border-[var(--border-soft)] px-3 py-2 text-xs">
                      <div className="text-white">{step.step_name}</div>
                      <div className="mt-1 text-[var(--text-muted)]">
                        {step.status} · {step.progress || 0}%
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      )}

      {videoUrl ? (
        <div className="mb-6">
          <VideoPlayer src={videoUrl} />
        </div>
      ) : null}

      {frames.length ? (
        <div className="mb-6 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-4">
          <StoryboardTimeline frames={frames} />
        </div>
      ) : null}

      {!frames.length ? (
        <div className="grid min-h-[360px] place-items-center rounded-lg border border-dashed border-[var(--border-soft)] bg-[var(--bg-secondary)] px-6 text-center">
          <div>
            <Film className="mx-auto mb-3 text-[var(--text-muted)]" size={34} />
            <p className="m-0 text-sm text-white">暂无分镜帧</p>
            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
              请先生成剧本，系统将自动创建初始分镜。
            </p>
          </div>
        </div>
      ) : null}

      {frames.length ? (
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
                    <img src={frame.image_url} alt={`Frame ${frame.sequence}`} className="h-full w-full object-cover" />
                  ) : (
                    <ImageIcon size={32} className="text-[var(--text-muted)]" />
                  )}
                </div>
                <div className="p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">分镜 {frame.sequence}</span>
                    <div className="flex items-center gap-2">
                      {frame.duration ? <span className="text-xs text-[var(--text-muted)]">{frame.duration}s</span> : null}
                      <span className={`text-xs ${status.color}`}>{status.text}</span>
                    </div>
                  </div>
                  <p className="mb-1 line-clamp-2 text-xs text-[var(--text-muted)]">
                    {frame.description || frame.image_prompt || '暂无提示词'}
                  </p>
                  {frame.subtitle_text || frame.text_overlay ? (
                    <p className="mb-1 line-clamp-1 text-xs text-[#a78bfa]">
                      字幕: {frame.subtitle_text || frame.text_overlay}
                    </p>
                  ) : null}
                  {frame.dirty ? (
                    <p className="mb-2 rounded-md bg-yellow-500/10 px-2 py-1 text-xs text-yellow-200">
                      需重新确认后续阶段
                    </p>
                  ) : null}
                  {frame.audio_url ? (
                    <div className="mb-2">
                      <audio controls src={frame.audio_url} className="h-7 w-full" />
                    </div>
                  ) : null}
                  {frame.status === 3 && frame.error_message ? (
                    <p className="mb-2 rounded-lg border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-xs text-red-200">
                      {frame.error_message}
                    </p>
                  ) : null}

                  <div className="grid gap-2">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => openEditFrame(frame)}
                        disabled={!!isRegenerating}
                        className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[var(--border-soft)] py-1.5 text-xs text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50"
                      >
                        <Edit3 size={12} />
                        编辑
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRegenerate(frame.id)}
                        disabled={!!isRegenerating}
                        className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[var(--border-soft)] py-1.5 text-xs text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50"
                      >
                        <RefreshCw size={12} className={isRegenerating === 'script' ? 'animate-spin' : ''} />
                        剧本
                      </button>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => handleRegenerateImage(frame.id)}
                        disabled={!!isRegenerating}
                        className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[var(--border-soft)] py-1.5 text-xs text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50"
                      >
                        <ImageIcon size={12} className={isRegenerating === 'image' ? 'animate-spin' : ''} />
                        图片
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRegenerateVideo(frame.id)}
                        disabled={!!isRegenerating || !frame.image_url}
                        className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[var(--border-soft)] py-1.5 text-xs text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50"
                      >
                        <Video size={12} className={isRegenerating === 'video' ? 'animate-spin' : ''} />
                        视频
                      </button>
                    </div>
                    {frame.status === 3 ? (
                      <button
                        type="button"
                        onClick={() => handleRetryFrame(frame.id)}
                        disabled={!!isRegenerating}
                        className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-red-500/40 px-2 py-1.5 text-xs text-red-200 hover:bg-red-500/10 disabled:opacity-50"
                      >
                        <RefreshCw size={12} className={isRegenerating === 'retry' ? 'animate-spin' : ''} />
                        重试失败的分镜
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ) : null}

      <PromptModal
        open={promptModal.open}
        title={
          promptModal.mode === 'script'
            ? '重新生成分镜剧本'
            : promptModal.mode === 'image'
              ? '重新生成分镜图片'
              : promptModal.mode === 'video'
                ? '重新生成分镜视频'
                : '重试失败的分镜'
        }
        description={
          activePromptFrame
            ? `正在更新分镜 ${activePromptFrame.sequence}，可添加可选的调整说明。`
            : ''
        }
        value={promptModal.value}
        setValue={(value) => setPromptModal((prev) => ({ ...prev, value }))}
        onClose={closePrompt}
        onConfirm={handleConfirmPrompt}
        loading={!!(promptModal.frameId && regenerating[promptModal.frameId])}
      />

      <FrameEditModal
        frame={editingFrame}
        form={editForm}
        setForm={setEditForm}
        saving={savingFrame}
        onClose={closeEditFrame}
        onSave={handleSaveFrameEdit}
      />
    </section>
  )
}
