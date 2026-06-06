import { useState, useEffect } from 'react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import LineChart from '../../components/Admin/Charts/LineChart'
import GaugeChart from '../../components/Admin/Charts/GaugeChart'
import Table from '../../components/Admin/Common/Table'
import { getSystemStats, getSystemLogs, getTraceStatistics } from '../../services/admin'
import { useAppStore } from '../../store/appStore'

const logColumns = [
  { key: 'time', title: '时间' },
  { key: 'level', title: '级别', render: (level) => (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
      level === 'error' ? 'bg-red-100 text-red-800' :
      level === 'warn' ? 'bg-yellow-100 text-yellow-800' :
      'bg-blue-100 text-blue-800'
    }`}>
      {level}
    </span>
  )},
  { key: 'message', title: '日志内容' },
  { key: 'source', title: '来源' },
]

// 模拟数据
const mockApiStats = [
  { time: '00:00', calls: 1200, errors: 12 },
  { time: '04:00', calls: 800, errors: 5 },
  { time: '08:00', calls: 2400, errors: 8 },
  { time: '12:00', calls: 3200, errors: 15 },
  { time: '16:00', calls: 2800, errors: 10 },
  { time: '20:00', calls: 1800, errors: 7 },
]

const mockLogs = [
  { time: '2026-06-05 14:30:00', level: 'info', message: '用户登录成功', source: 'auth' },
  { time: '2026-06-05 14:25:00', level: 'error', message: '数据库连接超时', source: 'database' },
  { time: '2026-06-05 14:20:00', level: 'warn', message: '内存使用率过高', source: 'system' },
  { time: '2026-06-05 14:15:00', level: 'info', message: '内容审核完成', source: 'content' },
  { time: '2026-06-05 14:10:00', level: 'error', message: 'API调用失败', source: 'api' },
]

export default function SystemMonitor() {
  const [loading, setLoading] = useState(true)
  const systemStats = useAppStore((state) => state.systemStats)
  const setSystemStats = useAppStore((state) => state.setSystemStats)
  const [logs, setLogs] = useState([])

  const fetchSystemStats = async () => {
    try {
      setLoading(true)
      // 获取系统资源监控数据
      const data = await getSystemStats()
      setSystemStats(data)
    } catch (error) {
      console.error('获取系统状态失败:', error)
      // 接口失败时使用默认值
      setSystemStats({
        cpuUsage: 0,
        memoryUsage: 0,
        diskUsage: 0,
        apiErrorRate: 0,
      })
    } finally {
      setLoading(false)
    }
  }

  const fetchLogs = async () => {
    try {
      // 获取系统日志
      const data = await getSystemLogs({ limit: 20 })
      setLogs(Array.isArray(data) ? data : data?.list || [])
    } catch (error) {
      console.error('获取系统日志失败:', error)
      // 接口失败时获取Agent追踪日志作为备选
      try {
        const traceData = await getTraceStatistics({ period: '1d' })
        setLogs(traceData?.recent_logs || [])
      } catch (e) {
        setLogs([])
      }
    }
  }

  useEffect(() => {
    fetchSystemStats()
    fetchLogs()
  }, [])

  if (loading) {
    return (
      <PageContainer title="系统监控">
        <div className="grid place-items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="系统监控">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <GaugeChart
          value={systemStats?.cpuUsage || 0}
          title="CPU使用率"
          color="#ef4444"
        />
        <GaugeChart
          value={systemStats?.memoryUsage || 0}
          title="内存使用率"
          color="#f59e0b"
        />
        <GaugeChart
          value={systemStats?.diskUsage || 0}
          title="磁盘使用率"
          color="#10b981"
        />
      </div>

      <div className="mb-6">
        <LineChart
          data={mockApiStats}
          xKey="time"
          yKey="calls"
          title="API调用趋势"
          color="#3b82f6"
        />
      </div>

      <div>
        <h3 className="text-lg font-semibold text-gray-800 mb-4">系统日志</h3>
        <Table
          columns={logColumns}
          data={logs}
          loading={loading}
        />
      </div>
    </PageContainer>
  )
}

