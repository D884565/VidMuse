import { useEffect, useState } from 'react'
import { X, Download } from 'lucide-react'
import {
  getProjectScripts,
  getProjectScript,
  downloadProjectVideo,
  getProjectDetail,
} from '../../services/project.js'

export default function ProjectDetail({ project, onClose }) {
  const [scriptDetail, setScriptDetail] = useState(null)
  const [frames, setFrames] = useState([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [videoUrl, setVideoUrl] = useState(project.video_output_url || '')

  useEffect(() => {
    let cancelled = false

    async function loadProjectData() {
      setLoading(true)
      try {
        const projectId = project.id
        const [scriptData, detail] = await Promise.all([
          getProjectScripts(projectId).catch(() => []),
          getProjectDetail(projectId).catch(() => null),
        ])

        if (cancelled) return

        const scriptSummaries = Array.isArray(scriptData) ? scriptData : scriptData?.scripts || []
        const latestScriptSummary = scriptSummaries[0] || null

        if (latestScriptSummary?.id) {
          const latestScriptDetail = await getProjectScript(projectId, latestScriptSummary.id).catch(() => null)
          if (!cancelled) {
            setScriptDetail(latestScriptDetail)
          }
        } else {
          setScriptDetail(null)
        }

        if (detail) {
          setFrames(detail.frames || [])
          if (detail.video_url || detail.video_output_url) {
            setVideoUrl(detail.video_url || detail.video_output_url)
          }
        } else {
          setFrames([])
          setVideoUrl(project.video_output_url || '')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadProjectData()

    return () => {
      cancelled = true
    }
  }, [project.id, project.video_output_url])

  const handleExport = async () => {
    setDownloading(true)
    try {
      await downloadProjectVideo(project.id)
    } catch (err) {
      alert('导出失败: ' + err.message)
    } finally {
      setDownloading(false)
    }
  }

  const scriptContent = scriptDetail?.content || {}
  const scenes = scriptContent.scenes || []
  const videoMeta = scriptContent.video_meta || {}

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative flex h-[85vh] w-[90vw] max-w-[1200px] overflow-hidden rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-sidebar)] shadow-2xl">
        <button
          className="absolute right-3 top-3 z-10 rounded-lg bg-[rgba(255,255,255,0.08)] p-2 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.15)] hover:text-white"
          onClick={onClose}
        >
          <X size={18} />
        </button>

        <div className="flex w-1/2 flex-col border-r border-[var(--border-soft)] p-6">
          <h2 className="m-0 mb-4 text-lg font-semibold">{project.title}</h2>

          <div className="flex-1 overflow-hidden rounded-xl bg-black">
            {videoUrl ? (
              <video
                src={videoUrl}
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

          {videoUrl && (
            <button
              className="mt-4 flex items-center justify-center gap-2 rounded-lg bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-4 py-2.5 text-sm font-medium shadow-[0_4px_24px_rgba(124,58,237,0.15)] hover:shadow-[0_4px_30px_rgba(124,58,237,0.35)] disabled:opacity-50"
              onClick={handleExport}
              disabled={downloading}
            >
              <Download size={16} />
              {downloading ? '导出中...' : '导出视频到本地'}
            </button>
          )}
        </div>

        <div className="flex w-1/2 flex-col overflow-y-auto p-6">
          <h3 className="m-0 mb-4 text-base font-semibold">剧本与分镜</h3>

          {loading ? (
            <div className="flex flex-1 items-center justify-center text-sm text-[var(--text-muted)]">
              加载中...
            </div>
          ) : (
            <div className="space-y-6">
              {videoMeta.style && (
                <div className="rounded-lg border border-[var(--border-soft)] bg-[rgba(26,26,46,0.5)] p-4">
                  <p className="m-0 mb-2 text-xs font-medium text-[var(--text-muted)]">视频风格</p>
                  <p className="m-0 text-sm">{videoMeta.style}</p>
                  {videoMeta.hook_line && (
                    <p className="m-0 mt-2 text-sm text-[#a78bfa]">"{videoMeta.hook_line}"</p>
                  )}
                </div>
              )}

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
                  const narration = frame?.narration || scene?.narration || scene?.text || ''

                  return (
                    <div
                      key={frame.id || frame.sequence || idx}
                      className="rounded-lg border border-[var(--border-soft)] bg-[rgba(26,26,46,0.5)] p-4"
                    >
                      <div className="mb-3 flex items-start gap-3">
                        {frame?.image_url && (
                          <img
                            src={frame.image_url}
                            alt={`分镜 ${frame.sequence || idx + 1}`}
                            className="h-20 w-28 shrink-0 rounded-lg object-cover"
                          />
                        )}
                        <div className="flex-1">
                          <p className="m-0 text-xs font-medium text-[#a78bfa]">
                            分镜 {frame.sequence || idx + 1}
                            {frame?.duration ? ` · ${frame.duration}s` : ''}
                          </p>
                          <p className="m-0 mt-1 text-sm text-white">{sceneDescription}</p>
                        </div>
                      </div>

                      {narration ? (
                        <p className="m-0 text-xs text-[var(--text-muted)]">旁白: {narration}</p>
                      ) : null}
                    </div>
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
    </div>
  )
}
