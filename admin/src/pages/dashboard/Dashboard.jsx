import { useState, useEffect } from 'react'
import { Cpu, Memory, HardDrive, Users, Clock, AlertTriangle } from 'lucide-react'
import PageContainer from '@/components/layout/PageContainer'
import StatCard from '@/components/common/StatCard'
import LineChart from '@/components/charts/LineChart'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import { getStats, getSystemMetrics, getRecentErrors } from '@/services/dashboard'

// 模拟数据
const mockCpuData = Array.from({ length: 12 }, (_, i) => ({
  time: `${i * 2}:00`,
  value: Math.floor(Math.random() * 40) + 30,
}))

const mockMemoryData = Array.from({ length: 12 }, (_, i) => ({
  time: `${i * 2}:00`,
  value: Math.floor(Math.random() * 30) + 40,
}))

const mockResponseTimeData = Array.from({ length: 12 }, (_, i) => ({
  time: `${i * 2}:00`,
  value: Math.floor(Math.random() * 200) + 100,
}))

const mockRecentErrors = [
  { id: 1, time: '10:24:32', path: '/api/video/upload', method: 'POST', status: 500, message: '存储空间不足' },
  { id: 2, time: '10:18:15', path: '/api/user/list', method: 'GET', status: 403, message: '权限不足' },
  { id: 3, time: '09:56:47', path: '/api/audio/transcode', method: 'POST', status: 504, message: '转码服务超时' },
  { id: 4, time: '09:32:19', path: '/api/image/process', method: 'POST', status: 400, message: '文件格式不支持' },
  { id: 5, time: '09:15:03', path: '/api/chat/message', method: 'GET', status: 502, message: '网关错误' },
]

function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    cpuUsage: '45%',
    memoryUsage: '62%',
    diskUsage: '78%',
    onlineUsers: '128',
    avgResponseTime: '156ms',
    successRate: '99.8%',
    qps: '234',
    totalRequests: '128,456',
    videoCount: '1,245',
    audioCount: '3,567',
    imageCount: '8,923',
    pendingAudit: '23',
  })
  const [recentErrors, setRecentErrors] = useState(mockRecentErrors)

  useEffect(() => {
    fetchData()
    // 每30秒刷新一次数据
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      // 实际项目中使用真实接口
      // const [statsRes, metricsRes, errorsRes] = await Promise.all([
      //   getStats(),
      //   getSystemMetrics(),
      //   getRecentErrors(),
      // ])
      // setStats(statsRes)
      // setRecentErrors(errorsRes)

      // 模拟加载
      setTimeout(() => {
        setLoading(false)
      }, 1000)
    } catch (error) {
      console.error('获取仪表盘数据失败', error)
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <PageContainer title="仪表盘">
      {/* 第一行：系统概览 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <StatCard
          title="CPU使用率"
          value={stats.cpuUsage}
          trend="up"
          trendValue="5.2%"
          icon={<Cpu size={24} />}
          color="primary"
        />
        <StatCard
          title="内存使用率"
          value={stats.memoryUsage}
          trend="down"
          trendValue="2.1%"
          icon={<Memory size={24} />}
          color="success"
        />
        <StatCard
          title="磁盘使用率"
          value={stats.diskUsage}
          trend="up"
          trendValue="3.5%"
          icon={<HardDrive size={24} />}
          color="warning"
        />
        <StatCard
          title="在线用户数"
          value={stats.onlineUsers}
          trend="up"
          trendValue="12.8%"
          icon={<Users size={24} />}
          color="primary"
        />
      </div>

      {/* 第二行：监控图表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="card p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-medium text-gray-500">CPU使用率趋势</h3>
            <span className="text-xs text-gray-300">近24小时</span>
          </div>
          <LineChart data={mockCpuData} xKey="time" yKey="value" color="#165DFF" />
        </div>
        <div className="card p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-medium text-gray-500">内存使用率趋势</h3>
            <span className="text-xs text-gray-300">近24小时</span>
          </div>
          <LineChart data={mockMemoryData} xKey="time" yKey="value" color="#00B42A" />
        </div>
      </div>

      {/* 第三行：接口统计 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <StatCard
          title="平均响应时间"
          value={stats.avgResponseTime}
          trend="down"
          trendValue="12ms"
          icon={<Clock size={24} />}
          color="success"
        />
        <StatCard
          title="请求成功率"
          value={stats.successRate}
          trend="up"
          trendValue="0.1%"
          icon={<AlertTriangle size={24} />}
          color="primary"
        />
        <StatCard
          title="QPS"
          value={stats.qps}
          trend="up"
          trendValue="8.3%"
          icon={<Clock size={24} />}
          color="warning"
        />
        <StatCard
          title="今日请求数"
          value={stats.totalRequests}
          trend="up"
          trendValue="15.6%"
          icon={<AlertTriangle size={24} />}
          color="primary"
        />
      </div>

      {/* 第四行：内容统计和异常列表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 内容统计 */}
        <div className="card p-6">
          <h3 className="font-medium text-gray-500 mb-4">内容统计</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary mr-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                </div>
                <span className="text-sm text-gray-500">视频总数</span>
              </div>
              <span className="font-medium text-gray-500">{stats.videoCount}</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center">
                <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center text-success mr-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 18V6l8 6-8 6z"></path>
                  </svg>
                </div>
                <span className="text-sm text-gray-500">音频总数</span>
              </div>
              <span className="font-medium text-gray-500">{stats.audioCount}</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center">
                <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center text-warning mr-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <circle cx="8.5" cy="8.5" r="1.5"></circle>
                    <polyline points="21 15 16 10 5 21"></polyline>
                  </svg>
                </div>
                <span className="text-sm text-gray-500">图片总数</span>
              </div>
              <span className="font-medium text-gray-500">{stats.imageCount}</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center">
                <div className="w-8 h-8 rounded-lg bg-danger/10 flex items-center justify-center text-danger mr-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                </div>
                <span className="text-sm text-gray-500">待审核内容</span>
              </div>
              <span className="font-medium text-danger">{stats.pendingAudit}</span>
            </div>
          </div>
        </div>

        {/* 最近异常 */}
        <div className="card p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-medium text-gray-500">最近异常</h3>
            <button className="text-xs text-primary hover:text-primary/80">查看全部</button>
          </div>
          <div className="space-y-3">
            {recentErrors.map((error) => (
              <div key={error.id} className="p-3 bg-gray-50 rounded-md">
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center">
                    <span className="px-2 py-0.5 bg-danger/10 text-danger text-xs rounded mr-2">
                      {error.status}
                    </span>
                    <span className="text-sm font-medium text-gray-500">{error.path}</span>
                  </div>
                  <span className="text-xs text-gray-300">{error.time}</span>
                </div>
                <p className="text-sm text-gray-400">{error.message}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PageContainer>
  )
}

export default Dashboard
