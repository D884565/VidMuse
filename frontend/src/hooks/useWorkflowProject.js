import { useEffect, useState } from 'react'
import { getProjectDetail } from '../services/project.js'

/**
 * 项目工作流状态轮询 Hook
 * 获取项目详情，并在任务运行中时每 3 秒自动轮询更新状态。
 * 返回 project、loading、error 和手动刷新函数 refetch。
 */
export function useWorkflowProject(projectId) {
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [refreshToken, setRefreshToken] = useState(0)

  useEffect(() => {
    if (!projectId) {
      setProject(null)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    let timer = null

    async function fetchProject() {
      setLoading(true)
      try {
        const data = await getProjectDetail(projectId)
        if (cancelled) return
        setProject(data)
        setError(null)
        // 任务运行中时，每 3 秒自动轮询
        if (data.stage_status === 'running') {
          timer = window.setTimeout(fetchProject, 3000)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchProject()

    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [projectId, refreshToken])

  return {
    project,
    loading,
    error,
    /** 手动触发刷新（通过递增 refreshToken） */
    refetch: () => setRefreshToken((value) => value + 1),
  }
}
