import { useState, useEffect, useCallback } from 'react'
import { getProjects } from '../services/project.js'

/**
 * 项目列表 hook
 * @param {Object} [initialParams] - 初始查询参数
 * @returns {{ projects, loading, error, refetch }}
 */
export function useProjects(initialParams = {}) {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [params] = useState(initialParams)

  const fetchProjects = useCallback(async () => {
    try {
      setLoading(true)
      const data = await getProjects(params)
      setProjects(data?.list ?? [])
      setError(null)
    } catch (err) {
      console.error('加载项目列表失败:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [params])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  return { projects, loading, error, refetch: fetchProjects }
}
