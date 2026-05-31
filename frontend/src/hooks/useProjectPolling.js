import { useState, useEffect, useRef } from 'react'
import { getProjectDetail } from '../services/project.js'

/**
 * 判断项目是否处于终态（应停止轮询）。
 * 以 workflow_stage / stage_status 为权威来源。
 */
function isProjectTerminal(data) {
  if (data.workflow_stage === 'completed') return true
  if (data.stage_status === 'failed') return true
  // created/idle 等待用户触发，不算终态，但也不需要轮询
  if (data.workflow_stage === 'created' && data.stage_status === 'idle') return true
  return false
}

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
  const [audioUrl, setAudioUrl] = useState(null)
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!projectId) {
      setProject(null)
      setFrames([])
      setVideoUrl(null)
      setAudioUrl(null)
      setAssets([])
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)

    async function fetchProject() {
      try {
        const data = await getProjectDetail(projectId)
        if (cancelled) return
        setProject(data)
        setFrames(data.frames || [])
        setVideoUrl(data.video_url || null)
        setAudioUrl(data.audio_url || null)
        setAssets(data.assets || [])
        setError(null)

        // 停止轮询：workflow 阶段为终态，或等待用户操作（running/awaiting_review 期间继续轮询）
        const workflowRunning = data.stage_status === 'running'
        const awaitingWorkflowReview = data.stage_status === 'awaiting_review'
        if (!workflowRunning && !awaitingWorkflowReview && isProjectTerminal(data)) {
          clearInterval(intervalRef.current)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    // 立即获取一次
    fetchProject()
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
    audioUrl,
    assets,
    loading,
    error,
    refetch: () => setRefreshToken((value) => value + 1),
  }
}
