import { useState, useEffect, useRef } from 'react'
import { getProjectDetail } from '../services/project.js'

/**
 * 项目状态轮询 hook
 * 每 3 秒获取一次项目详情，状态变为 completed 或 failed 时停止轮询
 * @param {string|null} projectId - 项目 ID
 * @returns {{ project, frames, loading, error }}
 */
export function useProjectPolling(projectId) {
  const [project, setProject] = useState(null)
  const [frames, setFrames] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!projectId) return

    let cancelled = false

    async function fetchProject() {
      try {
        const data = await getProjectDetail(projectId)
        if (cancelled) return
        setProject(data)
        setFrames(data.frames || [])
        setError(null)

        // 停止轮询：状态为 completed 或 failed
        if (data.status === 'completed' || data.status === 'failed') {
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
  }, [projectId])

  return { project, frames, loading, error }
}
