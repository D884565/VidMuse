import { useState, useEffect, useRef } from 'react'
import { getProjectDetail } from '../services/project.js'

// 需要停止轮询的状态
const TERMINAL_STATUSES = ['completed', 'failed', 'draft']

/**
 * 项目状态轮询 hook
 * 每 3 秒获取一次项目详情，状态变为终态时停止轮询
 * @param {string|null} projectId - 项目 ID
 * @returns {{ project, frames, videoUrl, audioUrl, assets, loading, error }}
 */
export function useProjectPolling(projectId) {
  const [project, setProject] = useState(null)
  const [frames, setFrames] = useState([])
  const [videoUrl, setVideoUrl] = useState(null)
  const [videoAssetId, setVideoAssetId] = useState(null)
  const [audioUrl, setAudioUrl] = useState(null)
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!projectId) {
      queueMicrotask(() => {
        setProject(null)
        setFrames([])
        setVideoUrl(null)
        setVideoAssetId(null)
        setAudioUrl(null)
        setAssets([])
        setLoading(false)
        setError(null)
      })
      return
    }

    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) setLoading(true)
    })

    async function fetchProject() {
      try {
        const data = await getProjectDetail(projectId)
        if (cancelled) return
        setProject(data)
        setFrames(data.frames || [])
        setVideoUrl(data.video_url || null)
        setVideoAssetId(data.video_asset_id || null)
        setAudioUrl(data.audio_url || null)
        setAssets(data.assets || [])
        setError(null)

        // 停止轮询：状态为终态
        const workflowRunning = data.stage_status === 'running'
        const awaitingWorkflowReview = data.stage_status === 'awaiting_review'
        if (TERMINAL_STATUSES.includes(data.status) && !workflowRunning && !awaitingWorkflowReview) {
          clearInterval(intervalRef.current)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    // 立即获取一次
    queueMicrotask(fetchProject)
    // 每 3 秒轮询
    intervalRef.current = setInterval(fetchProject, 3000)

    return () => {
      cancelled = true
      clearInterval(intervalRef.current)
    }
  }, [projectId, refreshToken])

  return {
    project,
    frames,
    videoUrl,
    videoAssetId,
    audioUrl,
    assets,
    loading,
    error,
    refetch: () => setRefreshToken((value) => value + 1),
  }
}
