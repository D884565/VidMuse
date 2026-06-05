import { useState, useEffect } from 'react'
import { Eye, Download, RefreshCw, BarChart3, PieChart, Clock, Users, Cpu, ChevronDown, ChevronRight } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import LineChart from '../../components/Admin/Charts/LineChart'
import GaugeChart from '../../components/Admin/Charts/GaugeChart'
import { getTraceList, getTraceDetail, getTraceStatistics, exportTraces } from '../../services/admin'

const columns = [
  {
    key: 'id',
    title: 'ID',
    render: (value) => <span className="text-sm font-medium text-gray-900">{value}</span>
  },
  {
    key: 'session_id',
    title: '会话ID',
    width: 120,
    render: (value) => <span className="text-sm font-mono text-gray-900">{value}</span>
  },
  {
    key: 'user_id',
    title: '用户ID',
    width: 80,
    render: (value) => <span className="text-sm text-gray-900">{value || '-'}</span>
  },
  {
    key: 'project_id',
    title: '项目ID',
    width: 80,
    render: (value) => <span className="text-sm text-gray-900">{value || '-'}</span>
  },
  {
    key: 'model',
    title: '使用模型',
    width: 150,
    render: (value) => <span className="text-sm font-medium text-gray-900">{value}</span>
  },
  {
    key: 'iterations',
    title: '迭代次数',
    width: 80,
    render: (iterations) => (
      <span className="text-sm font-medium text-gray-900">{iterations || 0}</span>
    )
  },
  {
    key: 'success',
    title: '状态',
    width: 80,
    render: (success) => (
      <span className={`px-2 py-1 rounded-full text-xs font-bold ${
        success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}>
        {success ? '成功' : '失败'}
      </span>
    )
  },
  {
    key: 'cost_time',
    title: '耗时',
    width: 80,
    render: (cost_time) => (
      <span className="text-sm font-medium text-gray-900">{(cost_time * 1000).toFixed(0)}ms</span>
    )
  },
  {
    key: 'temperature',
    title: '温度',
    width: 80,
    render: (temp) => (
      <span className="text-sm font-medium text-gray-900">{temp || 0}</span>
    )
  },
  {
    key: 'created_at',
    title: '创建时间',
    width: 160,
    render: (value) => <span className="text-sm text-gray-900">{value}</span>
  },
]

const periodOptions = [
  { value: '1d', label: '最近1天' },
  { value: '7d', label: '最近7天' },
  { value: '30d', label: '最近30天' },
  { value: 'all', label: '全部' },
]

export default function TraceManagement() {
  const [loading, setLoading] = useState(true)
  const [traces, setTraces] = useState([])
  const [statistics, setStatistics] = useState(null)
  const [filters, setFilters] = useState({
    session_id: '',
    user_id: '',
    project_id: '',
    model: '',
    success: '',
    keyword: '',
    period: '7d',
    page: 1,
    page_size: 20,
  })
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: 20 })
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentTrace, setCurrentTrace] = useState(null)
  const [trendData, setTrendData] = useState([])
  const [modelDistribution, setModelDistribution] = useState([])
  const [durationDistribution, setDurationDistribution] = useState([])

  useEffect(() => {
    fetchData()
  }, [filters.page, filters.period])

  const fetchData = async () => {
    try {
      setLoading(true)
      // 获取轨迹列表
      const listParams = Object.fromEntries(
        Object.entries(filters).filter(([_, v]) => v !== '' && v != null)
      )
      const listData = await getTraceList(listParams)
      setTraces(Array.isArray(listData) ? listData : listData?.list || [])
      setPagination({
        total: listData?.total || listData?.length || 0,
        page: listParams.page || 1,
        page_size: listParams.page_size || 20,
      })

      // 获取统计数据
      const statData = await getTraceStatistics({ period: filters.period })
      setStatistics(statData)

      // 生成趋势图数据（模拟）
      setTrendData(generateTrendData(statData))
      // 生成模型分布和耗时分布数据
      setModelDistribution(generateModelDistribution())
      setDurationDistribution(generateDurationDistribution())
    } catch (error) {
      console.error('获取追踪数据失败:', error)
      setTraces([])
      setStatistics(null)
    } finally {
      setLoading(false)
    }
  }

  const generateTrendData = (stats) => {
    // 生成最近7天的趋势数据
    const days = Array.from({ length: 7 }, (_, i) => {
      const date = new Date()
      date.setDate(date.getDate() - 6 + i)
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    })

    return days.map((day, index) => ({
      day,
      calls: Math.floor(Math.random() * 500) + 200,
      success_rate: 80 + Math.random() * 15,
      avg_duration: 1000 + Math.random() * 2000,
    }))
  }

  // 生成模型使用分布数据
  const generateModelDistribution = () => {
    return [
      { name: 'Claude 3 Opus', value: 45 },
      { name: 'Claude 3 Sonnet', value: 30 },
      { name: 'GPT-4o', value: 15 },
      { name: '其他模型', value: 10 },
    ]
  }

  // 生成耗时分布数据
  const generateDurationDistribution = () => {
    return [
      { range: '<1s', count: 35 },
      { range: '1-3s', count: 45 },
      { range: '3-5s', count: 12 },
      { range: '5-10s', count: 6 },
      { range: '>10s', count: 2 },
    ]
  }

  // 递归渲染Span树形结构
  const renderSpanTree = (spans, level = 0) => {
    if (!spans || spans.length === 0) return null

    return spans.map(span => (
      <div key={span.span_id} className="mb-2">
        <div className={`flex items-center p-2 rounded ${span.has_exception ? 'bg-red-50' : 'bg-gray-50'}`} style={{ marginLeft: `${level * 20}px` }}>
          {span.child_spans && span.child_spans.length > 0 ? (
            <span className="mr-2 cursor-pointer">
              {span.expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
          ) : (
            <span className="mr-2 w-4"></span>
          )}
          <span className="font-mono text-xs text-gray-500 mr-2">{span.duration_ms}ms</span>
          <span className="font-medium text-sm mr-2">{span.name}</span>
          <span className="text-xs text-gray-400">{span.module_name}</span>
          {span.has_exception && (
            <span className="ml-2 text-xs text-red-500">⚠️ 异常</span>
          )}
        </div>
        {span.expanded && span.child_spans && renderSpanTree(span.child_spans, level + 1)}
      </div>
    ))
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }))
  }

  const handleViewDetail = async (traceId) => {
    try {
      const detail = await getTraceDetail(traceId)
      setCurrentTrace(detail)
      setDetailVisible(true)
    } catch (error) {
      console.error('获取详情失败:', error)
      alert('获取详情失败，请重试')
    }
  }

  const handleExport = async () => {
    try {
      const params = Object.fromEntries(
        Object.entries(filters).filter(([_, v]) => v !== '' && v != null)
      )
      await exportTraces(params)
      alert('导出成功，文件已开始下载')
    } catch (error) {
      console.error('导出失败:', error)
      alert('导出失败，请重试')
    }
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
      title="链路追踪管理"
      actions={
        <div className="flex space-x-2">
          <button
            onClick={handleExport}
            className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Download size={20} />
            <span>导出数据</span>
          </button>
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
                <p className="text-sm text-gray-500 mb-1">总调用次数</p>
                <h3 className="text-2xl font-bold text-gray-800">{statistics.total_count?.toLocaleString() || 0}</h3>
              </div>
              <BarChart3 className="text-blue-500" size={24} />
            </div>
            <div className="mt-2 text-sm">
              <span className="text-green-500">{statistics.success_count || 0} 成功</span>
              <span className="text-gray-400 mx-2">|</span>
              <span className="text-red-500">{statistics.failed_count || 0} 失败</span>
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
            <div className={`mt-2 text-sm ${statistics.success_rate >= 0.95 ? 'text-green-500' : statistics.success_rate >= 0.8 ? 'text-yellow-500' : 'text-red-500'}`}>
              {statistics.success_rate >= 0.95 ? '优秀' : statistics.success_rate >= 0.8 ? '良好' : '需要优化'}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">平均响应时间</p>
                <h3 className="text-2xl font-bold text-gray-800">{((statistics.avg_cost_time || 0) * 1000).toFixed(0)}ms</h3>
              </div>
              <Clock className="text-orange-500" size={24} />
            </div>
            <div className="mt-2 text-sm text-blue-500">
              总工具调用 {statistics.total_tool_calls || 0} 次
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">平均迭代次数</p>
                <h3 className="text-2xl font-bold text-gray-800">{statistics.avg_iterations?.toFixed(1) || 0}</h3>
              </div>
              <Cpu className="text-purple-500" size={24} />
            </div>
            <div className="mt-2 text-sm text-purple-500">
              统计周期: {statistics.period || '7d'}
            </div>
          </div>
        </div>
      )}

      {/* 趋势图 */}
      {trendData.length > 0 && (
        <div className="mb-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <LineChart
            data={trendData}
            xKey="day"
            yKey="calls"
            title="调用量趋势"
            color="#3b82f6"
          />
          <LineChart
            data={trendData}
            xKey="day"
            yKey="success_rate"
            title="成功率趋势"
            color="#10b981"
          />
          <LineChart
            data={trendData}
            xKey="day"
            yKey="avg_duration"
            title="平均耗时趋势"
            color="#f59e0b"
          />
        </div>
      )}

      {/* 分布统计 */}
      {modelDistribution.length > 0 && durationDistribution.length > 0 && (
        <div className="mb-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 模型使用分布 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">模型使用分布</h3>
            <div className="space-y-3">
              {modelDistribution.map((item, index) => {
                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444']
                return (
                  <div key={index} className="flex items-center">
                    <div className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: colors[index % colors.length] }}></div>
                    <div className="flex-1">
                      <div className="flex justify-between text-sm mb-1">
                        <span>{item.name}</span>
                        <span className="font-medium">{item.value}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="h-2 rounded-full"
                          style={{ width: `${item.value}%`, backgroundColor: colors[index % colors.length] }}
                        ></div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 耗时分布 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">请求耗时分布</h3>
            <div className="flex items-end h-48 justify-between">
              {durationDistribution.map((item, index) => {
                const maxCount = Math.max(...durationDistribution.map(d => d.count))
                const height = (item.count / maxCount) * 100
                return (
                  <div key={index} className="flex flex-col items-center flex-1 mx-1">
                    <div
                      className="w-full bg-blue-500 rounded-t-sm"
                      style={{ height: `${height}%` }}
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
      <div className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
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
          <label className="block text-sm font-medium text-gray-700 mb-1">会话ID</label>
          <input
            type="text"
            placeholder="会话ID"
            value={filters.session_id}
            onChange={(e) => handleFilterChange('session_id', e.target.value)}
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
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">项目ID</label>
          <input
            type="number"
            placeholder="项目ID"
            value={filters.project_id}
            onChange={(e) => handleFilterChange('project_id', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">状态</label>
          <select
            value={filters.success}
            onChange={(e) => handleFilterChange('success', e.target.value === '' ? '' : e.target.value === 'true')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部</option>
            <option value="true">成功</option>
            <option value="false">失败</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">关键词搜索</label>
          <input
            type="text"
            placeholder="搜索问题/回答"
            value={filters.keyword}
            onChange={(e) => handleFilterChange('keyword', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            onKeyDown={(e) => e.key === 'Enter' && fetchData()}
          />
        </div>
      </div>

      {/* 轨迹列表 */}
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
            onClick={() => handleFilterChange('page', Math.max(1, pagination.page - 1))}
            disabled={pagination.page <= 1}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <button
            onClick={() => handleFilterChange('page', pagination.page + 1)}
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
          <div className="bg-white rounded-lg w-full max-w-4xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">推理详情 #{currentTrace.id}</h3>
              <button onClick={() => setDetailVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* 基础信息 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">会话ID</label>
                  <p className="text-sm font-mono bg-gray-50 p-2 rounded">{currentTrace.session_id || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">用户ID</label>
                  <p className="text-sm">{currentTrace.user_id || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">项目ID</label>
                  <p className="text-sm">{currentTrace.project_id || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">使用模型</label>
                  <p className="text-sm">{currentTrace.model || '-'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">参数配置</label>
                  <p className="text-sm">
                    温度: {currentTrace.temperature || 0},
                    最大Token: {currentTrace.max_tokens || 0},
                    迭代: {currentTrace.iterations || 0}次
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">耗时</label>
                  <p className="text-sm">{(currentTrace.cost_time * 1000).toFixed(0)}ms</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">状态</label>
                  <p className={`text-sm ${currentTrace.success ? 'text-green-600' : 'text-red-600'}`}>
                    {currentTrace.success ? '成功' : '失败'}
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">创建时间</label>
                  <p className="text-sm">{currentTrace.created_at || '-'}</p>
                </div>
              </div>

              {/* 用户输入 */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">用户输入</label>
                <div className="bg-gray-50 p-3 rounded-lg text-sm whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {currentTrace.user_input || '-'}
                </div>
              </div>

              {/* 系统提示词 */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">系统提示词</label>
                <div className="bg-yellow-50 p-3 rounded-lg text-sm whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {currentTrace.system_prompt || '-'}
                </div>
              </div>

              {/* 最终回答 */}
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-2">AI回答</label>
                <div className="bg-blue-50 p-3 rounded-lg text-sm whitespace-pre-wrap max-h-60 overflow-y-auto">
                  {currentTrace.final_answer || '-'}
                </div>
              </div>

              {/* 工具调用 */}
              {currentTrace.tool_calls && currentTrace.tool_calls.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-2">工具调用 ({currentTrace.tool_calls.length}次)</label>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    {currentTrace.tool_calls.map((call, index) => (
                      <div key={index} className="mb-3 last:mb-0">
                        <p className="text-sm font-medium text-purple-600 mb-1">
                          工具 {index + 1}: {call.name}
                        </p>
                        <pre className="text-xs bg-white p-2 rounded overflow-x-auto">
                          {JSON.stringify(call.parameters, null, 2)}
                        </pre>
                        {/* 工具返回结果 */}
                        {currentTrace.tool_results && currentTrace.tool_results[index] && (
                          <div className="mt-2">
                            <p className="text-xs font-medium text-green-600 mb-1">返回结果:</p>
                            <pre className="text-xs bg-green-50 p-2 rounded overflow-x-auto">
                              {typeof currentTrace.tool_results[index] === 'string'
                                ? currentTrace.tool_results[index]
                                : JSON.stringify(currentTrace.tool_results[index], null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 消息历史 */}
              {currentTrace.messages_history && currentTrace.messages_history.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-2">对话历史 ({currentTrace.messages_history.length}轮)</label>
                  <div className="bg-gray-50 p-3 rounded-lg max-h-80 overflow-y-auto">
                    {currentTrace.messages_history.map((msg, index) => (
                      <div key={index} className={`mb-3 last:mb-0 p-2 rounded ${
                        msg.role === 'user' ? 'bg-white' :
                        msg.role === 'assistant' ? 'bg-blue-50' : 'bg-gray-100'
                      }`}>
                        <p className="text-xs font-medium mb-1 text-gray-500">
                          {msg.role === 'user' ? '用户' : msg.role === 'assistant' ? 'AI' : '系统'}:
                        </p>
                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 错误信息 */}
              {currentTrace.error_msg && (
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-2">错误信息</label>
                  <div className="bg-red-50 p-3 rounded-lg text-sm text-red-600 whitespace-pre-wrap">
                    {currentTrace.error_msg}
                  </div>
                </div>
              )}

              {/* 元数据 */}
              {currentTrace.metadata && Object.keys(currentTrace.metadata).length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-2">扩展元数据</label>
                  <pre className="bg-gray-50 p-3 rounded-lg text-xs overflow-x-auto">
                    {JSON.stringify(currentTrace.metadata, null, 2)}
                  </pre>
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
