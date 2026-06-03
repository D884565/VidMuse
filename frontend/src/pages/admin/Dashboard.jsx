import { useState, useEffect } from 'react'
import { Activity, CheckCircle2, XCircle, Clock, Wrench } from 'lucide-react'
import StatCard from '../../components/Admin/StatCard.jsx'
import { getTraceStats } from '../../services/adminTrace.js'

export default function AdminDashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('7d')

  useEffect(() => {
    loadStats()
  }, [period])

  const loadStats = async () => {
    try {
      setLoading(true)
      const data = await getTraceStats({ period })
      setStats(data)
    } catch (error) {
      console.error('加载统计数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-[var(--bg-sidebar)]/50 rounded" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="h-32 bg-[var(--bg-sidebar)]/50 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">统计概览</h1>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="bg-[var(--bg-sidebar)] border border-[var(--border-soft)] rounded-lg px-3 py-2 text-sm"
        >
          <option value="1d">最近1天</option>
          <option value="7d">最近7天</option>
          <option value="30d">最近30天</option>
          <option value="all">全部时间</option>
        </select>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <StatCard
          title="总调用次数"
          value={stats?.total_count || 0}
          icon={<Activity size={20} />}
        />
        <StatCard
          title="成功次数"
          value={stats?.success_count || 0}
          icon={<CheckCircle2 size={20} className="text-green-500" />}
          className="border-green-500/20"
        />
        <StatCard
          title="失败次数"
          value={stats?.failed_count || 0}
          icon={<XCircle size={20} className="text-red-500" />}
          className="border-red-500/20"
        />
        <StatCard
          title="成功率"
          value={`${((stats?.success_rate || 0) * 100).toFixed(1)}`}
          unit="%"
          icon={<Activity size={20} className="text-blue-500" />}
        />
        <StatCard
          title="平均耗时"
          value={(stats?.avg_cost_time || 0).toFixed(2)}
          unit="s"
          icon={<Clock size={20} className="text-yellow-500" />}
        />
        <StatCard
          title="工具调用次数"
          value={stats?.total_tool_calls || 0}
          icon={<Wrench size={20} className="text-purple-500" />}
        />
      </div>

      {/* 图表区域预留 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] p-5">
          <h3 className="text-lg font-medium mb-4">调用趋势</h3>
          <div className="h-[300px] flex items-center justify-center text-[var(--text-muted)]">
            图表功能开发中
          </div>
        </div>
        <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] p-5">
          <h3 className="text-lg font-medium mb-4">模型使用占比</h3>
          <div className="h-[300px] flex items-center justify-center text-[var(--text-muted)]">
            图表功能开发中
          </div>
        </div>
      </div>
    </div>
  )
}
