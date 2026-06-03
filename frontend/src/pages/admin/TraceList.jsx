import { useState, useEffect } from 'react'
import TraceFilter from '../../components/Admin/TraceFilter.jsx'
import TraceTable from '../../components/Admin/TraceTable.jsx'
import { getTraceList } from '../../services/adminTrace.js'

export default function AdminTraceList() {
  const [traces, setTraces] = useState([])
  const [loading, setLoading] = useState(true)
  const [pagination, setPagination] = useState({
    total: 0,
    page: 1,
    page_size: 20
  })
  const [filters, setFilters] = useState({
    session_id: '',
    user_id: '',
    project_id: '',
    model: '',
    success: undefined,
    start_time: '',
    end_time: '',
    keyword: ''
  })

  useEffect(() => {
    loadTraceList()
  }, [pagination.page, pagination.page_size])

  const loadTraceList = async () => {
    try {
      setLoading(true)
      const params = {
        ...filters,
        page: pagination.page,
        page_size: pagination.page_size
      }
      // 过滤掉空值参数
      Object.keys(params).forEach(key => {
        if (params[key] === '' || params[key] === undefined || params[key] === null) {
          delete params[key]
        }
      })
      const data = await getTraceList(params)
      setTraces(data.list)
      setPagination(prev => ({
        ...prev,
        total: data.total,
        page: data.page,
        page_size: data.page_size
      }))
    } catch (error) {
      console.error('加载轨迹列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setPagination(prev => ({ ...prev, page: 1 }))
    loadTraceList()
  }

  const handlePageChange = (newPage) => {
    setPagination(prev => ({ ...prev, page: newPage }))
  }

  const handlePageSizeChange = (e) => {
    setPagination({
      page: 1,
      page_size: Number(e.target.value),
      total: 0
    })
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">推理轨迹</h1>
      </div>

      {/* 筛选区域 */}
      <TraceFilter
        filters={filters}
        onFilterChange={setFilters}
        onSearch={handleSearch}
      />

      {/* 表格区域 */}
      <TraceTable
        traces={traces}
        loading={loading}
      />

      {/* 分页区域 */}
      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
          <span>共 {pagination.total} 条</span>
          <select
            value={pagination.page_size}
            onChange={handlePageSizeChange}
            className="bg-[var(--bg-sidebar)] border border-[var(--border-soft)] rounded px-2 py-1 text-xs"
          >
            <option value={10}>10条/页</option>
            <option value={20}>20条/页</option>
            <option value={50}>50条/页</option>
            <option value={100}>100条/页</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled={pagination.page <= 1}
            onClick={() => handlePageChange(pagination.page - 1)}
            className="px-3 py-1.5 bg-[var(--bg-sidebar)] border border-[var(--border-soft)] rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg)] transition-colors"
          >
            上一页
          </button>
          <span className="text-sm">
            第 {pagination.page} 页 / 共 {Math.ceil(pagination.total / pagination.page_size) || 1} 页
          </span>
          <button
            disabled={pagination.page >= Math.ceil(pagination.total / pagination.page_size)}
            onClick={() => handlePageChange(pagination.page + 1)}
            className="px-3 py-1.5 bg-[var(--bg-sidebar)] border border-[var(--border-soft)] rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg)] transition-colors"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  )
}
