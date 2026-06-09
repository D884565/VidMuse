import { useCallback, useState, useEffect, useRef } from 'react'
import { getProjectDetail } from '../services/project.js'

/**
 * 判断项目是否处于终态（应停止轮询）。
 * 以 workflow_stage / stage_status 为权威来源。
 */
function isProjectTerminal(data) {
  if (data.workflow_stage === 'completed') return true
  // failed 但有 last_task_id 时不立即停止，让 FrameGrid 有机会恢复任务并显示错误
  if (data.stage_status === 'failed' && !data.last_task_id) return true
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
  const stableFetchCountRef = useRef(0)
  const lastSnapshotRef = useRef(null)

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  const applyFrameUpdates = useCallback((updatedFrames = []) => {
    if (!Array.isArray(updatedFrames) || updatedFrames.length === 0) return
    setFrames((currentFrames) => {
      const patchById = new Map(updatedFrames.map((frame) => [frame.frame_id || frame.id, frame]))
      return currentFrames.map((frame) => {
        const patch = patchById.get(frame.id)
        return patch ? { ...frame, ...patch, id: patch.id || patch.frame_id || frame.id } : frame
      })
    })
  }, [])

  const applyProjectSnapshot = useCallback((snapshot = {}) => {
    if (!snapshot?.workflow_stage && !snapshot?.stage_status && !snapshot?.task_id) return
    setProject((currentProject) => {
      if (!currentProject) return currentProject
      return {
        ...currentProject,
        workflow_stage: snapshot.workflow_stage || currentProject.workflow_stage,
        stage_status: snapshot.stage_status || currentProject.stage_status,
        dirty_stage: snapshot.dirty_stage ?? currentProject.dirty_stage,
        last_task_id: snapshot.task_id ?? snapshot.last_task_id ?? currentProject.last_task_id,
      }
    })
  }, [])

  useEffect(() => {
    if (!projectId) {
      return
    }

    let cancelled = false
    stableFetchCountRef.current = 0

    async function fetchProject() {
      if (cancelled) return

      // 只在首次加载时显示 loading，轮询时不闪烁
      if (!project) setLoading(true)
      try {
        const data = await getProjectDetail(projectId)
        if (cancelled) return
        setProject(data)
        setFrames(data.frames || [])
        setVideoUrl(data.video_output_url || data.video_url || null)
        setAudioUrl(data.audio_url || null)
        setAssets(data.assets || [])
        setError(null)
        const snapshot = [
          data.workflow_stage,
          data.stage_status,
          data.last_task_id,
          data.video_output_url,
          data.video_url,
          data.audio_url,
        ].join('|')
        if (lastSnapshotRef.current !== snapshot) {
          stableFetchCountRef.current = 0
          lastSnapshotRef.current = snapshot
        }

        // 停止轮询：workflow 阶段为终态，或等待用户操作（running/awaiting_review 期间继续轮询）
        const workflowRunning = data.stage_status === 'running'
        const stableReview = data.stage_status === 'awaiting_review'
        const stableTerminal = isProjectTerminal(data)
        if (!workflowRunning && (stableReview || stableTerminal)) {
          stableFetchCountRef.current += 1
          if (stableFetchCountRef.current >= 2) {
            stopPolling()
          }
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
      stopPolling()
    }
  }, [projectId, refreshToken])

  // When no projectId, return default empty state
  if (!projectId) {
    return {
      project: null,
      frames: [],
      videoUrl: null,
      audioUrl: null,
      assets: [],
      loading: false,
      error: null,
      refetch: () => {},
      applyFrameUpdates: () => {},
      applyProjectSnapshot: () => {},
    }
  }

  return {
    project,
    frames,
    videoUrl,
    audioUrl,
    assets,
    loading,
    error,
    refetch: () => setRefreshToken((value) => value + 1),
    applyFrameUpdates,
    applyProjectSnapshot,
  }
}
