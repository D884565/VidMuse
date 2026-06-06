import { useState, useEffect, useCallback } from 'react'
import { getProjects } from '../services/project.js'
import { useAppStore } from '../store/appStore.js'

/**
 * 项目列表 hook。
 * @param {Object} [initialParams] 初始查询参数
 * @returns {{ projects, loading, error, refetch }}
 */
export function useProjects(initialParams = {}) {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [params] = useState(initialParams)
  const projectListVersion = useAppStore((state) => state.projectListVersion)

  const fetchProjects = useCallback(async (options = {}) => {
    const { cancelledRef } = options
    try {
      setLoading(projects.length === 0)
      const data = await getProjects(params)
      if (cancelledRef?.current) return
      setProjects(data?.list ?? [])
      setError(null)
    } catch (err) {
      console.error('加载项目列表失败:', err)
      if (cancelledRef?.current) return
      setError(err.message)
    } finally {
      if (!cancelledRef?.current) setLoading(false)
    }
  }, [params, projects.length])

  useEffect(() => {
    const cancelledRef = { current: false }
    queueMicrotask(() => fetchProjects({ cancelledRef }))
    return () => {
      // 组件卸载后停止写入 state，避免异步请求晚返回造成警告。
      cancelledRef.current = true
    }
  }, [fetchProjects, projectListVersion])

  return { projects, loading, error, refetch: fetchProjects }
}
