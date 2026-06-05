import { useEffect, useState } from 'react'
import { Users, FileImage, Activity, Layers } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import StatCard from '../../components/Admin/Common/StatCard'
import LineChart from '../../components/Admin/Charts/LineChart'
import { getDashboardStats } from '../../services/admin'
import { useAppStore } from '../../store/appStore'

// 模拟数据
const mockUserGrowth = [
  { date: '1月', users: 120 },
  { date: '2月', users: 180 },
  { date: '3月', users: 220 },
  { date: '4月', users: 280 },
  { date: '5月', users: 350 },
  { date: '6月', users: 420 },
]

const mockContentGrowth = [
  { date: '1月', content: 80 },
  { date: '2月', content: 120 },
  { date: '3月', content: 180 },
  { date: '4月', content: 240 },
  { date: '5月', content: 310 },
  { date: '6月', content: 380 },
]

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const stats = useAppStore((state) => state.adminStats)
  const setAdminStats = useAppStore((state) => state.setAdminStats)

  const fetchStats = async () => {
    try {
      setLoading(true)
      const data = await getDashboardStats()
      setAdminStats(data)
    } catch (error) {
      console.error('获取统计数据失败:', error)
      // 接口调用失败时使用默认值
      setAdminStats({
        totalUsers: 0,
        totalContent: 0,
        systemStatus: '异常',
        apiCalls: 0,
        userGrowth: 0,
        contentGrowth: 0,
        apiGrowth: 0,
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

  if (loading) {
    return (
      <PageContainer title="数据概览">
        <div className="grid place-items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="数据概览">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <StatCard
          title="总用户数"
          value={stats?.totalUsers || 0}
          trend="up"
          trendValue={stats?.userGrowth || 0}
          icon={Users}
          color="blue"
        />
        <StatCard
          title="总内容数"
          value={stats?.totalContent || 0}
          trend="up"
          trendValue={stats?.contentGrowth || 0}
          icon={FileImage}
          color="green"
        />
        <StatCard
          title="系统状态"
          value={stats?.systemStatus || '正常'}
          icon={Activity}
          color="purple"
        />
        <StatCard
          title="接口调用量"
          value={stats?.apiCalls?.toLocaleString() || 0}
          trend="up"
          trendValue={stats?.apiGrowth || 0}
          icon={Layers}
          color="orange"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <LineChart
          data={mockUserGrowth}
          xKey="date"
          yKey="users"
          title="用户增长趋势"
          color="#3b82f6"
        />
        <LineChart
          data={mockContentGrowth}
          xKey="date"
          yKey="content"
          title="内容增长趋势"
          color="#10b981"
        />
      </div>
    </PageContainer>
  )
}

