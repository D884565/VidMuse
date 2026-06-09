import { useEffect, useMemo, useState } from 'react'
import { X, Download, Edit3, Film, Image as ImageIcon, Loader2, Save } from 'lucide-react'
import { appendVideoCacheBuster } from '../../utils/mediaUrl.js'
import { appendImageCacheBuster } from '../../utils/mediaUrl.js'
import {
  downloadProjectVideo,
  getGenerationTask,
  getProjectDetail,
  getProjectScript,
  getProjectScripts,
} from '../../services/project.js'
import { regenerateFrameImage, regenerateFrameVideo, updateFrame } from '../../services/frame.js'
import { useAppStore } from '../../store/appStore.js'
import { formatVideoStyle } from '../../utils/videoStyle.js'

const DEFAULT_FORM = {
  narration: '',
  subtitle_text: '',
  subtitle_position: 'bottom',
  image_prompt: '',
  video_prompt: '',
  duration: 3,
  sequence: 1,
}

const TASK_POLL_INTERVAL_MS = 1500
const TERMINAL_TASK_STATUSES = new Set(['succeeded', 'failed', 'cancelled', 'completed'])

function buildFrameForm(frame) {
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

function FrameEditorPanel({
  frame,
  form,
  onChange,
  onClose,
  onSave,
  onRegenerateImage,
  onRegenerateVideo,
  saving,
  actionLoading,
  canRegenerateVideo,
  mustRegenerateImageFirst,
}) {
  if (!frame) return null

  return (
    <div className="rounded-xl border border-[var(--border-soft)] bg-[rgba(18,18,34,0.92)] p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="m-0 text-sm font-semibold text-white">编辑分镜 {frame.sequence}</p>
          <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
            修改后可先保存草稿，或直接重新生成图片并继续后续视频生成。
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-[var(--border-soft)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.06)]"
        >
          关闭
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-xs text-[var(--text-muted)]">
          顺序
          <input
            type="number"
            value={form.sequence}
            onChange={(event) => onChange('sequence', Number(event.target.value || 1))}
            className="mt-1 w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-3 py-2 text-sm text-white outline-none focus:border-[#7C3AED]"
          />
        </label>
        <label className="text-xs text-[var(--text-muted)]">
          时长
          <input
            type="number"
            step="1"
            value={form.duration}
            onChange={(event) => onChange('duration', Math.round(Number(event.target.value || 1)))}
            className="mt-1 w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-3 py-2 text-sm text-white outline-none focus:border-[#7C3AED]"
          />
        </label>
        <label className="text-xs text-[var(--text-muted)] md:col-span-2">
          旁白
          <textarea
            rows={3}
            value={form.narration}
            onChange={(event) => onChange('narration', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-3 py-2 text-sm text-white outline-none focus:border-[#7C3AED]"
          />
        </label>
        <label className="text-xs text-[var(--text-muted)] md:col-span-2">
          字幕
          <input
            type="text"
            value={form.subtitle_text}
            onChange={(event) => onChange('subtitle_text', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-3 py-2 text-sm text-white outline-none focus:border-[#7C3AED]"
          />
        </label>
        <label className="text-xs text-[var(--text-muted)]">
          字幕位置
          <input
            type="text"
            value={form.subtitle_position}
            onChange={(event) => onChange('subtitle_position', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-3 py-2 text-sm text-white outline-none focus:border-[#7C3AED]"
          />
        </label>
        <div />
        <label className="text-xs text-[var(--text-muted)] md:col-span-2">
          图片提示词
          <textarea
            rows={3}
            value={form.image_prompt}
            onChange={(event) => onChange('image_prompt', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-3 py-2 text-sm text-white outline-none focus:border-[#7C3AED]"
          />
        </label>
        <label className="text-xs text-[var(--text-muted)] md:col-span-2">
          视频提示词
          <textarea
            rows={3}
            value={form.video_prompt}
            onChange={(event) => onChange('video_prompt', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-3 py-2 text-sm text-white outline-none focus:border-[#7C3AED]"
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={saving || !!actionLoading}
          className="inline-flex items-center gap-2 rounded-lg bg-[#7C3AED] px-3 py-2 text-sm text-white hover:bg-[#6d28d9] disabled:opacity-50"
        >
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存草稿
        </button>
        <button
          type="button"
          onClick={onRegenerateImage}
          disabled={saving || !!actionLoading}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-soft)] px-3 py-2 text-sm text-white hover:bg-[rgba(255,255,255,0.06)] disabled:opacity-50"
        >
          {actionLoading === 'image' ? <Loader2 size={16} className="animate-spin" /> : <ImageIcon size={16} />}
          重新生成图片
        </button>
        <button
          type="button"
          onClick={onRegenerateVideo}
          disabled={saving || !!actionLoading || !canRegenerateVideo}
          title={mustRegenerateImageFirst ? '请先重新生成图片' : undefined}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-soft)] px-3 py-2 text-sm text-white hover:bg-[rgba(255,255,255,0.06)] disabled:opacity-50"
        >
          {actionLoading === 'video' ? <Loader2 size={16} className="animate-spin" /> : <Film size={16} />}
          重新生成视频
        </button>
      </div>
      {mustRegenerateImageFirst ? (
        <p className="m-0 mt-2 text-xs text-amber-200">请先重新生成图片，再生成视频。</p>
      ) : null}
    {/* 编辑分镜 */}
    </div>
  )
}

export default function ProjectDetail({ project, onClose }) {
  const [projectSnapshot, setProjectSnapshot] = useState(project)
  const [scriptDetail, setScriptDetail] = useState(null)
  const [frames, setFrames] = useState([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [videoUrl, setVideoUrl] = useState(project.video_output_url || '')
  const [editorOpen, setEditorOpen] = useState(false)
  const [selectedFrameId, setSelectedFrameId] = useState(null)
  const [editForm, setEditForm] = useState(DEFAULT_FORM)
  const [savingFrame, setSavingFrame] = useState(false)
  const [actionLoading, setActionLoading] = useState('')
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')
  const bumpConversationVersion = useAppStore((state) => state.bumpConversationVersion)

  const selectedFrame = useMemo(
    () => frames.find((frame) => frame.id === selectedFrameId) || null,
    [frames, selectedFrameId]
  )
  const displayVideoUrl = useMemo(
    () => appendVideoCacheBuster(videoUrl, projectSnapshot.updated_at, projectSnapshot.last_task_id),
    [projectSnapshot.last_task_id, projectSnapshot.updated_at, videoUrl]
  )
  const mustRegenerateImageFirst = !!selectedFrame && (
    !selectedFrame.image_url || Number(selectedFrame.status) !== 2 || !!selectedFrame.dirty
  )
  const canRegenerateVideo = !!selectedFrame && !mustRegenerateImageFirst

  useEffect(() => {
    if (selectedFrame) {
      setEditForm(buildFrameForm(selectedFrame))
    } else {
      setEditForm(DEFAULT_FORM)
    }
  }, [selectedFrame])

  const scriptContent = scriptDetail?.content || {}
  const scenes = scriptContent.scenes || []
  const videoMeta = scriptContent.video_meta || {}
  const videoStyleLabel = formatVideoStyle(videoMeta.style)

  const loadProjectData = async ({ clearMessages = false } = {}) => {
    if (clearMessages) {
      setFeedback('')
      setError('')
    }
    setLoading(true)
    try {
      const [scriptData, detail] = await Promise.all([
        getProjectScripts(project.id).catch(() => []),
        getProjectDetail(project.id).catch(() => null),
      ])
      const scriptSummaries = Array.isArray(scriptData) ? scriptData : scriptData?.scripts || []
      const latestScriptSummary = scriptSummaries[0] || null

      if (latestScriptSummary?.id) {
        const latestScriptDetail = await getProjectScript(project.id, latestScriptSummary.id).catch(() => null)
        setScriptDetail(latestScriptDetail)
      } else {
        setScriptDetail(null)
      }

      if (detail) {
        setProjectSnapshot(detail)
        const nextFrames = detail.frames || []
        setFrames(nextFrames)
        setVideoUrl(detail.video_url || detail.video_output_url || project.video_output_url || '')
        setSelectedFrameId((currentId) => {
          if (!nextFrames.length) return null
          if (currentId && nextFrames.some((frame) => frame.id === currentId)) return currentId
          return nextFrames[0].id
        })
      } else {
        setProjectSnapshot(project)
        setFrames([])
        setVideoUrl(project.video_output_url || '')
        setSelectedFrameId(null)
      }
    } catch (err) {
      setError(err.message || '加载项目详情失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setProjectSnapshot(project)
  }, [project])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      if (cancelled) return
      await loadProjectData()
    }

    bootstrap()

    return () => {
      cancelled = true
    }
  }, [project.id, project.video_output_url])

  const handleRefresh = async () => {
    await loadProjectData()
  }

  const handleExport = async () => {
    setDownloading(true)
    try {
      await downloadProjectVideo(project.id)
    } catch (err) {
      setError(`导出失败: ${err.message}`)
    } finally {
      setDownloading(false)
    }
  }

  const handleFormChange = (field, value) => {
    setEditForm((prev) => ({ ...prev, [field]: value }))
  }

  const buildFramePatch = () => ({
    ...editForm,
    duration: Number(editForm.duration || 0),
    sequence: Number(editForm.sequence || selectedFrame?.sequence || 1),
  })

  const validateDraft = () => {
    if (!selectedFrame) return
    const targetDuration = Number(project.target_duration || videoMeta.target_duration || 0)
    if (!targetDuration) return

    const totalDuration = frames.reduce((sum, frame) => {
      const duration = frame.id === selectedFrame.id ? Number(editForm.duration || 0) : Number(frame.duration || 0)
      return sum + duration
    }, 0)

    if (totalDuration - targetDuration > 0.001) {
      setFeedback(`分镜总时长 ${Math.round(totalDuration)} 秒，已超过项目目标时长 ${Math.round(targetDuration)} 秒，请注意调整。`)
    }
  }

  const saveFrameDraft = async () => {
    if (!selectedFrame) return null
    validateDraft()
    const frame = await updateFrame(project.id, selectedFrame.id, buildFramePatch())
    bumpConversationVersion()
    return frame
  }

  const waitForTaskCompletion = async (taskId) => {
    if (!taskId) return null

    while (true) {
      const task = await getGenerationTask(taskId)
      if (TERMINAL_TASK_STATUSES.has(task.status)) {
        if (task.status === 'succeeded' || task.status === 'completed') {
          return task
        }
        throw new Error(task.error_message || '图片重新生成失败')
      }
      await new Promise((resolve) => setTimeout(resolve, TASK_POLL_INTERVAL_MS))
    }
  }

  const handleSaveFrame = async () => {
    if (!selectedFrame) return
    setSavingFrame(true)
    setFeedback('')
    setError('')
    try {
      const savedFrame = await saveFrameDraft()
      await handleRefresh()
      setFeedback(`分镜 ${savedFrame?.sequence || selectedFrame.sequence} 草稿已保存，对话记录已同步。`)
    } catch (err) {
      setError(err.message || '保存分镜失败')
    } finally {
      setSavingFrame(false)
    }
  }

  const handleRegenerateImage = async () => {
    if (!selectedFrame) return
    setActionLoading('image')
    setFeedback('')
    setError('')
    try {
      const savedFrame = await saveFrameDraft()
      const result = await regenerateFrameImage(project.id, selectedFrame.id, '')
      bumpConversationVersion()
      await handleRefresh()
      await waitForTaskCompletion(result?.task_id)
      await handleRefresh()
      setFeedback(`分镜 ${savedFrame?.sequence || selectedFrame.sequence} 的图片已更新，可以继续生成新视频。`)
    } catch (err) {
      setError(err.message || '重新生成图片失败')
    } finally {
      setActionLoading('')
    }
  }

  const handleRegenerateVideo = async () => {
    if (!selectedFrame) return
    if (!canRegenerateVideo) {
      setFeedback('请先重新生成图片，再生成视频。')
      return
    }
    setActionLoading('video')
    setFeedback('')
    setError('')
    try {
      await saveFrameDraft()
      const result = await regenerateFrameVideo(project.id, selectedFrame.id, '')
      bumpConversationVersion()
      await handleRefresh()
      await waitForTaskCompletion(result?.task_id)
      await handleRefresh()
      setFeedback(`分镜 ${selectedFrame.sequence} 的视频片段已更新。`)
    } catch (err) {
      setError(err.message || '重新生成视频失败')
    } finally {
      setActionLoading('')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative flex h-[88vh] w-[94vw] max-w-[1320px] overflow-hidden rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-sidebar)] shadow-2xl">
        <button
          className="absolute right-3 top-3 z-10 rounded-lg bg-[rgba(255,255,255,0.08)] p-2 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.15)] hover:text-white"
          onClick={onClose}
        >
          <X size={18} />
        </button>

        <div className="flex w-[46%] flex-col border-r border-[var(--border-soft)] p-6">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="m-0 text-lg font-semibold">{project.title}</h2>
              <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
                {frames.some((frame) => frame.dirty) ? '存在待应用的分镜修改' : '当前分镜与成片已同步'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setEditorOpen((value) => !value)}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-soft)] px-3 py-2 text-sm text-white hover:bg-[rgba(255,255,255,0.06)]"
            >
              <Edit3 size={16} />
              {editorOpen ? '收起编辑' : '编辑分镜'}
            </button>
          </div>

          <div className="flex-1 overflow-hidden rounded-xl bg-black">
            {videoUrl ? (
              <video
                key={displayVideoUrl}
                src={displayVideoUrl}
                controls
                className="h-full w-full"
                preload="metadata"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-[var(--text-muted)]">
                暂无视频
              </div>
            )}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {videoUrl ? (
              <button
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-4 py-2.5 text-sm font-medium shadow-[0_4px_24px_rgba(124,58,237,0.15)] hover:shadow-[0_4px_30px_rgba(124,58,237,0.35)] disabled:opacity-50"
                onClick={handleExport}
                disabled={downloading}
              >
                <Download size={16} />
                {downloading ? '导出中...' : '导出视频'}
              </button>
            ) : null}
          </div>
        </div>

        <div className="flex w-[54%] flex-col overflow-y-auto p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h3 className="m-0 text-base font-semibold">剧本与分镜</h3>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleRegenerateImage}
                disabled={!selectedFrame || savingFrame || !!actionLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-soft)] px-3 py-2 text-sm text-white hover:bg-[rgba(255,255,255,0.06)] disabled:opacity-50"
              >
                {actionLoading === 'image' ? <Loader2 size={16} className="animate-spin" /> : <ImageIcon size={16} />}
                重新生成图片
              </button>
              <button
                type="button"
                onClick={handleRegenerateVideo}
                disabled={!selectedFrame || savingFrame || !!actionLoading || !canRegenerateVideo}
                title={mustRegenerateImageFirst ? '请先重新生成图片' : undefined}
                className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-soft)] px-3 py-2 text-sm text-white hover:bg-[rgba(255,255,255,0.06)] disabled:opacity-50"
              >
                {actionLoading === 'video' ? <Loader2 size={16} className="animate-spin" /> : <Film size={16} />}
                重新生成视频
              </button>
            </div>
          </div>

          {feedback ? (
            <div className="mb-3 rounded-lg border border-[rgba(167,139,250,0.25)] bg-[rgba(124,58,237,0.12)] px-3 py-2 text-xs text-[#d8b4fe]">
              {feedback}
            </div>
          ) : null}
          {error ? (
            <div className="mb-3 rounded-lg border border-[rgba(248,113,113,0.25)] bg-[rgba(127,29,29,0.25)] px-3 py-2 text-xs text-red-300">
              {error}
            </div>
          ) : null}

          {loading ? (
            <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-muted)]">
              加载中...
            </div>
          ) : (
            <div className="space-y-6">
              {videoStyleLabel ? (
                <div className="rounded-lg border border-[var(--border-soft)] bg-[rgba(26,26,46,0.5)] p-4">
                  <p className="m-0 mb-2 text-xs font-medium text-[var(--text-muted)]">视频风格</p>
                  <p className="m-0 text-sm">{videoStyleLabel}</p>
                  {videoMeta.hook_line ? (
                    <p className="m-0 mt-2 text-sm text-[#a78bfa]">"{videoMeta.hook_line}"</p>
                  ) : null}
                </div>
              ) : null}

              {editorOpen ? (
                <FrameEditorPanel
                  frame={selectedFrame}
                  form={editForm}
                  onChange={handleFormChange}
                  onClose={() => setEditorOpen(false)}
                  onSave={handleSaveFrame}
                  onRegenerateImage={handleRegenerateImage}
                  onRegenerateVideo={handleRegenerateVideo}
                  saving={savingFrame}
                  actionLoading={actionLoading}
                  canRegenerateVideo={canRegenerateVideo}
                  mustRegenerateImageFirst={mustRegenerateImageFirst}
                />
              ) : null}

              {frames.length > 0 ? (
                frames.map((frame, idx) => {
                  const scene = scenes.find((item, sceneIndex) => sceneIndex + 1 === frame.sequence) || null
                  const sceneDescription =
                    frame?.description ||
                    frame?.image_prompt ||
                    scene?.description ||
                    scene?.visual?.description ||
                    scene?.visual?.image_prompt ||
                    '无描述'
                  const videoPrompt =
                    frame?.video_prompt ||
                    frame?.prompt ||
                    scene?.visual?.video_prompt ||
                    ''
                  const narration = frame?.narration || scene?.narration || scene?.text || ''
                  const isSelected = frame.id === selectedFrameId

                  return (
                    <button
                      key={frame.id || frame.sequence || idx}
                      type="button"
                      onClick={() => {
                        setSelectedFrameId(frame.id)
                        setEditorOpen(true)
                      }}
                      className={`w-full rounded-lg border p-4 text-left transition ${
                        isSelected
                          ? 'border-[#8b5cf6] bg-[rgba(76,29,149,0.25)]'
                          : 'border-[var(--border-soft)] bg-[rgba(26,26,46,0.5)] hover:bg-[rgba(40,40,68,0.65)]'
                      }`}
                    >
                      <div className="mb-3 flex items-start gap-3">
                        {frame?.image_url ? (
                          <img
                            src={appendImageCacheBuster(
                              frame.image_url,
                              frame.updated_at,
                              projectSnapshot.updated_at,
                              projectSnapshot.last_task_id
                            )}
                            alt={`分镜 ${frame.sequence || idx + 1}`}
                            className="h-20 w-28 shrink-0 rounded-lg object-cover"
                          />
                        ) : null}
                        <div className="flex-1">
                          <p className="m-0 text-xs font-medium text-[#a78bfa]">
                            分镜 {frame.sequence || idx + 1}
                            {frame?.dirty ? ' · 待应用修改' : ''}
                          </p>
                          <p className="m-0 mt-1 text-sm text-white">{sceneDescription}</p>
                          {videoPrompt ? (
                            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">视频: {videoPrompt}</p>
                          ) : null}
                        </div>
                      </div>

                      {narration ? (
                        <p className="m-0 text-xs text-[var(--text-muted)]">旁白: {narration}</p>
                      ) : null}
                    </button>
                  )
                })
              ) : (
                <div className="flex flex-1 items-center justify-center py-10 text-sm text-[var(--text-muted)]">
                  暂无剧本数据
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      {/* 编辑分镜 */}
    </div>
  )
}
