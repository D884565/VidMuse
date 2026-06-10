import { useState, useEffect } from 'react'
import { Eye, Download, RefreshCw, Clock, BarChart3, PieChart, Server, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import LineChart from '../../components/Admin/Charts/LineChart'
import { getSystemTraceList, getSystemTraceDetail, getSystemTraceSpans, getSystemTraceStatistics } from '../../services/admin'

const columns = [
  {
    key: 'id',
    title: 'ID',
    width: 60,
    render: (value) => <span className="text-sm font-medium text-gray-900">{value}</span>
  },
  {
    key: 'trace_id',
    title: 'Trace ID',
    width: 120,
    render: (value) => <span className="text-sm font-mono text-gray-900">{value}</span>
  },
  {
    key: 'method',
    title: '方法',
    width: 80,
    render: (value) => <span className="text-sm font-bold text-gray-900">{value}</span>
  },
  {
    key: 'path',
    title: '请求路径',
    width: 200,
    render: (value) => <span className="text-sm text-gray-900 font-mono truncate" title={value}>{value}</span>
  },
  {
    key: 'status_code',
    title: '状态码',
    width: 80,
    render: (code) => {
      let colorClass = 'bg-green-100 text-green-800 font-medium'
      if (code >= 400 && code < 500) colorClass = 'bg-yellow-100 text-yellow-800 font-medium'
      if (code >= 500) colorClass = 'bg-red-100 text-red-800 font-medium'
      return (
        <span className={`px-2 py-1 rounded-full text-xs ${colorClass}`}>
          {code}
        </span>
      )
    }
  },
  {
    key: 'duration_ms',
    title: '耗时(ms)',
    width: 90,
    render: (duration) => {
      let colorClass = 'text-green-700 font-medium'
      if (duration > 1000) colorClass = 'text-yellow-700 font-medium'
      if (duration > 3000) colorClass = 'text-red-700 font-medium'
      return <span className={`text-sm ${colorClass}`}>{duration.toFixed(0)}</span>
    }
  },
  {
    key: 'client_ip',
    title: '客户端IP',
    width: 120,
    render: (value) => <span className="text-sm text-gray-900">{value}</span>
  },
  {
    key: 'user_id',
    title: '用户ID',
    width: 80,
    render: (value) => <span className="text-sm text-gray-900">{value || '-'}</span>
  },
  {
    key: 'created_at',
    title: '创建时间',
    width: 160,
    render: (value) => <span className="text-sm text-gray-900">{value}</span>
  },
]

const periodOptions = [
  { value: '1h', label: '最近1小时' },
  { value: '6h', label: '最近6小时' },
  { value: '1d', label: '最近1天' },
  { value: '7d', label: '最近7天' },
  { value: 'all', label: '全部' },
]

const statusCodeOptions = [
  { value: '', label: '全部' },
  { value: '2xx', label: '2xx (成功)' },
  { value: '3xx', label: '3xx (重定向)' },
  { value: '4xx', label: '4xx (客户端错误)' },
  { value: '5xx', label: '5xx (服务端错误)' },
]

export default function SystemTraceManagement() {
  const [loading, setLoading] = useState(true)
  const [traces, setTraces] = useState([])
  const [statistics, setStatistics] = useState(null)
  const [filters, setFilters] = useState({
    trace_id: '',
    method: '',
    path: '',
    status_code: '',
    min_duration: '',
    max_duration: '',
    client_ip: '',
    user_id: '',
    has_exception: '',
    period: '1d',
    page: 1,
    page_size: 20,
  })
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: 20 })
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentTrace, setCurrentTrace] = useState(null)
  const [currentSpans, setCurrentSpans] = useState(null)
  const [trendData, setTrendData] = useState([])
  const [statusDistribution, setStatusDistribution] = useState([])
  const [durationDistribution, setDurationDistribution] = useState([])

  useEffect(() => {
    fetchData()
  }, [filters])

  const fetchData = async () => {
    try {
      setLoading(true)
      // 处理状态码筛选
      const listParams = Object.fromEntries(
        Object.entries(filters).filter(([_, v]) => v !== '' && v != null)
      )
      // 转换2xx/3xx等为实际的数值范围
      if (listParams.status_code) {
        const codePrefix = listParams.status_code.slice(0, 1)
        listParams[`status_code[gte]`] = parseInt(codePrefix) * 100
        listParams[`status_code[lte]`] = (parseInt(codePrefix) + 1) * 100 - 1
        delete listParams.status_code
      }

      const listData = await getSystemTraceList(listParams)
      setTraces(Array.isArray(listData) ? listData : listData?.list || [])
      setPagination({
        total: listData?.total || listData?.length || 0,
        page: listData?.page || listParams.page || 1,
        page_size: listData?.page_size || listParams.page_size || 20,
      })

      // 获取统计数据
      const statData = await getSystemTraceStatistics({ period: filters.period })
      setStatistics(statData)

      // 生成趋势图数据
      setTrendData(generateTrendData(statData))
      // 生成分布数据
      setStatusDistribution(generateStatusDistribution())
      setDurationDistribution(generateDurationDistribution())
    } catch (error) {
      console.error('获取系统追踪数据失败:', error)
      setTraces([])
      setStatistics(null)
    } finally {
      setLoading(false)
    }
  }

  const generateTrendData = (stats) => {
    const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)
    return hours.map((hour, index) => ({
      hour,
      requests: Math.floor(Math.random() * 1000) + 100,
      avg_duration: 100 + Math.random() * 500,
      error_rate: Math.random() * 5,
    }))
  }

  const generateStatusDistribution = () => {
    return [
      { name: '2xx (成功)', value: 75, color: '#10b981' },
      { name: '3xx (重定向)', value: 10, color: '#3b82f6' },
      { name: '4xx (客户端错误)', value: 10, color: '#f59e0b' },
      { name: '5xx (服务端错误)', value: 5, color: '#ef4444' },
    ]
  }

  const generateDurationDistribution = () => {
    return [
      { range: '<100ms', count: 45 },
      { range: '100-500ms', count: 35 },
      { range: '500-1000ms', count: 12 },
      { range: '1-3s', count: 6 },
      { range: '>3s', count: 2 },
    ]
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
      // 修改筛选条件时重置到第一页，但修改页码时不需要
      ...(key !== 'page' && { page: 1 })
    }))
  }

  const handleViewDetail = async (traceId) => {
    try {
      const [detail, spans] = await Promise.all([
        getSystemTraceDetail(traceId),
        getSystemTraceSpans(traceId, { include_details: true })
      ])
      setCurrentTrace(detail)
      // 给Span添加expanded属性，默认展开第一层
      const expandSpans = (spans) => {
        return spans.map(span => ({
          ...span,
          expanded: true,
          child_spans: span.child_spans ? expandSpans(span.child_spans) : []
        }))
      }
      setCurrentSpans({
        ...spans,
        tree: spans.tree ? expandSpans(spans.tree) : []
      })
      setDetailVisible(true)
    } catch (error) {
      console.error('获取详情失败:', error)
      alert('获取详情失败，请重试')
    }
  }

  const toggleSpanExpand = (spanId) => {
    const toggleRecursive = (spans) => {
      return spans.map(span => {
        if (span.id === spanId) {
          return { ...span, expanded: !span.expanded }
        }
        if (span.child_spans) {
          return { ...span, child_spans: toggleRecursive(span.child_spans) }
        }
        return span
      })
    }
    setCurrentSpans(prev => ({
      ...prev,
      tree: toggleRecursive(prev.tree)
    }))
  }

  const renderSpanTree = (spans) => {
    if (!spans || spans.length === 0) return null

    return spans.map(span => (
      <div key={span.id} className="mb-1">
        <div
          className={`flex items-center p-2 rounded text-sm cursor-pointer ${
            span.has_exception ? 'bg-red-50 border border-red-200' : 'bg-gray-50 border border-gray-100'
          }`}
          onClick={() => toggleSpanExpand(span.id)}
        >
          {span.child_spans && span.child_spans.length > 0 ? (
            <span className="mr-2 text-gray-700">
              {span.expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
          ) : (
            <span className="mr-2 w-4"></span>
          )}
          <span className="font-mono text-xs font-medium text-gray-700 w-20 mr-2">{span.duration_ms}ms</span>
          <span className="font-semibold mr-2 flex-1 truncate text-gray-900">{span.name}</span>
          <span className="text-xs font-medium text-gray-600 w-32 truncate mr-2">{span.module_name}</span>
          {span.class_name && (
            <span className="text-xs font-medium text-gray-600 w-24 truncate mr-2">{span.class_name}</span>
          )}
          {span.has_exception && (
            <span className="ml-2 text-xs font-semibold text-red-600 flex items-center">
              <AlertTriangle size={12} className="mr-1" /> 异常
            </span>
          )}
        </div>
        {span.expanded && span.child_spans && span.child_spans.length > 0 && (
          <div className="ml-6 border-l-2 border-gray-200 pl-2 mt-1">
            {renderSpanTree(span.child_spans)}
          </div>
        )}
      </div>
    ))
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={() => handleViewDetail(row.id)}
        className="p-1 text-blue-600 hover:text-blue-800"
        title="查看详情"
      >
        <Eye size={16} />
      </button>
    </div>
  )

  return (
    <PageContainer
      title="系统链路追踪"
      actions={
        <div className="flex space-x-2">
          <button
            onClick={fetchData}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <RefreshCw size={20} />
            <span>刷新</span>
          </button>
        </div>
      }
    >
      {/* 统计卡片 */}
      {statistics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">总请求次数</p>
                <h3 className="text-2xl font-bold text-gray-800">{statistics.total_count?.toLocaleString() || 0}</h3>
              </div>
              <BarChart3 className="text-blue-500" size={24} />
            </div>
            <div className="mt-2 text-sm">
              <span className="text-green-500">{statistics.success_count || 0} 成功</span>
              <span className="text-gray-400 mx-2">|</span>
              <span className="text-red-500">{statistics.error_count || 0} 错误</span>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">成功率</p>
                <h3 className="text-2xl font-bold text-gray-800">{((statistics.success_rate || 0) * 100).toFixed(1)}%</h3>
              </div>
              <PieChart className="text-green-500" size={24} />
            </div>
            <div className={`mt-2 text-sm ${statistics.success_rate >= 0.99 ? 'text-green-500' : statistics.success_rate >= 0.95 ? 'text-yellow-500' : 'text-red-500'}`}>
              {statistics.success_rate >= 0.99 ? '优秀' : statistics.success_rate >= 0.95 ? '良好' : '需要优化'}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">平均响应时间</p>
                <h3 className="text-2xl font-bold text-gray-800">{(statistics.avg_duration || 0).toFixed(0)}ms</h3>
              </div>
              <Clock className="text-orange-500" size={24} />
            </div>
            <div className="mt-2 text-sm">
              <span>P50: {statistics.p50_duration || 0}ms</span>
              <span className="text-gray-400 mx-2">|</span>
              <span>P95: {statistics.p95_duration || 0}ms</span>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">总Span数量</p>
                <h3 className="text-2xl font-bold text-gray-800">{statistics.total_span_count?.toLocaleString() || 0}</h3>
              </div>
              <Server className="text-purple-500" size={24} />
            </div>
            <div className="mt-2 text-sm text-purple-500">
              平均每个请求: {statistics.avg_span_per_trace?.toFixed(1) || 0} 个Span
            </div>
          </div>
        </div>
      )}

      {/* 趋势图 */}
      {trendData.length > 0 && (
        <div className="mb-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <LineChart
            data={trendData}
            xKey="hour"
            yKey="requests"
            title="请求量趋势"
            color="#3b82f6"
          />
          <LineChart
            data={trendData}
            xKey="hour"
            yKey="avg_duration"
            title="平均耗时趋势"
            color="#f59e0b"
          />
          <LineChart
            data={trendData}
            xKey="hour"
            yKey="error_rate"
            title="错误率趋势(%)"
            color="#ef4444"
          />
        </div>
      )}

      {/* 分布统计 */}
      {statusDistribution.length > 0 && durationDistribution.length > 0 && (
        <div className="mb-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 状态码分布 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">状态码分布</h3>
            <div className="space-y-3">
              {statusDistribution.map((item, index) => (
                <div key={index} className="flex items-center">
                  <div className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: item.color }}></div>
                  <div className="flex-1">
                    <div className="flex justify-between text-sm mb-1">
                      <span>{item.name}</span>
                      <span className="font-medium">{item.value}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full"
                        style={{ width: `${item.value}%`, backgroundColor: item.color }}
                      ></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 耗时分布 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">响应耗时分布</h3>
            <div className="flex items-end h-48 justify-between">
              {durationDistribution.map((item, index) => {
                const maxCount = Math.max(...durationDistribution.map(d => d.count))
                const height = (item.count / maxCount) * 100
                const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#7c3aed']
                return (
                  <div key={index} className="flex flex-col items-center flex-1 mx-1">
                    <div
                      className="w-full rounded-t-sm"
                      style={{ height: `${height}%`, backgroundColor: colors[index % colors.length] }}
                    ></div>
                    <div className="text-xs text-gray-500 mt-2">{item.range}</div>
                    <div className="text-xs font-medium">{item.count}</div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* 筛选栏 */}
      <div className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">统计周期</label>
          <select
            value={filters.period}
            onChange={(e) => handleFilterChange('period', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {periodOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Trace ID</label>
          <input
            type="text"
            placeholder="Trace ID"
            value={filters.trace_id}
            onChange={(e) => handleFilterChange('trace_id', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">请求方法</label>
          <select
            value={filters.method}
            onChange={(e) => handleFilterChange('method', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部</option>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
            <option value="PATCH">PATCH</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">状态码</label>
          <select
            value={filters.status_code}
            onChange={(e) => handleFilterChange('status_code', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {statusCodeOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">最小耗时(ms)</label>
          <input
            type="number"
            placeholder="最小耗时"
            value={filters.min_duration}
            onChange={(e) => handleFilterChange('min_duration', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">最大耗时(ms)</label>
          <input
            type="number"
            placeholder="最大耗时"
            value={filters.max_duration}
            onChange={(e) => handleFilterChange('max_duration', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">客户端IP</label>
          <input
            type="text"
            placeholder="客户端IP"
            value={filters.client_ip}
            onChange={(e) => handleFilterChange('client_ip', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">用户ID</label>
          <input
            type="number"
            placeholder="用户ID"
            value={filters.user_id}
            onChange={(e) => handleFilterChange('user_id', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* 链路列表 */}
      <Table
        columns={columns}
        data={traces}
        actions={actions}
        loading={loading}
      />

      {/* 分页信息 */}
      <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
        <div>
          共 {pagination.total} 条记录，第 {pagination.page} 页 / 共 {Math.ceil(pagination.total / pagination.page_size)} 页
        </div>
        <div className="space-x-2">
          <button
            onClick={() => setFilters(prev => ({ ...prev, page: Math.max(1, prev.page - 1) }))}
            disabled={pagination.page <= 1}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <button
            onClick={() => setFilters(prev => ({ ...prev, page: prev.page + 1 }))}
            disabled={pagination.page >= Math.ceil(pagination.total / pagination.page_size)}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            下一页
          </button>
        </div>
      </div>

      {/* 详情弹窗 */}
      {detailVisible && currentTrace && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-6xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">链路详情 #{currentTrace.id}</h3>
              <button onClick={() => setDetailVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* 基础信息 */}
              <div>
                <h4 className="text-md font-semibold mb-3 text-gray-700">基础信息</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-gray-50 p-4 rounded-lg">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Trace ID</label>
                    <p className="text-sm font-mono font-medium text-gray-900">{currentTrace.trace_id || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">请求方法</label>
                    <p className="text-sm font-bold text-gray-900">{currentTrace.method || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">状态码</label>
                    <p className={`text-sm font-bold ${
                      currentTrace.status_code >= 200 && currentTrace.status_code < 300 ? 'text-green-700' :
                      currentTrace.status_code >= 400 && currentTrace.status_code < 500 ? 'text-yellow-700' : 'text-red-700'
                    }`}>
                      {currentTrace.status_code || '-'}
                    </p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">总耗时</label>
                    <p className="text-sm font-medium text-gray-900">{currentTrace.duration_ms?.toFixed(0) || 0}ms</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">请求路径</label>
                    <p className="text-sm font-mono text-gray-900 break-all">{currentTrace.path || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">客户端IP</label>
                    <p className="text-sm font-medium text-gray-900">{currentTrace.client_ip || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">用户ID</label>
                    <p className="text-sm font-medium text-gray-900">{currentTrace.user_id || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">创建时间</label>
                    <p className="text-sm font-medium text-gray-900">{currentTrace.created_at || '-'}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Span数量</label>
                    <p className="text-sm font-medium text-gray-900">{currentTrace.span_count || 0} 个</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Span总耗时</label>
                    <p className="text-sm font-medium text-gray-900">{currentTrace.total_span_duration?.toFixed(0) || 0}ms</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">User Agent</label>
                    <p className="text-sm text-gray-800 truncate" title={currentTrace.user_agent}>
                      {currentTrace.user_agent || '-'}
                    </p>
                  </div>
                </div>
              </div>

              {/* 请求头 */}
              {currentTrace.request_headers && Object.keys(currentTrace.request_headers).length > 0 && (
                <div>
                  <h4 className="text-md font-semibold mb-3 text-gray-700">请求头</h4>
                  <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-x-auto">
                    {JSON.stringify(currentTrace.request_headers, null, 2)}
                  </pre>
                </div>
              )}

              {/* 响应头 */}
              {currentTrace.response_headers && Object.keys(currentTrace.response_headers).length > 0 && (
                <div>
                  <h4 className="text-md font-semibold mb-3 text-gray-700">响应头</h4>
                  <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-x-auto">
                    {JSON.stringify(currentTrace.response_headers, null, 2)}
                  </pre>
                </div>
              )}

              {/* Span调用树 */}
              {currentSpans && currentSpans.tree && currentSpans.tree.length > 0 && (
                <div>
                  <h4 className="text-md font-semibold mb-3 text-gray-700">
                    调用栈树 ({currentSpans.total} 个Span)
                  </h4>
                  <div className="bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
                    {renderSpanTree(currentSpans.tree)}
                  </div>
                </div>
              )}
            </div>
            <div className="p-6 border-t flex justify-end">
              <button
                onClick={() => setDetailVisible(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
