import { useState, useEffect } from 'react'
import { ArrowLeft, Clock, User, Hash, Calendar, CheckCircle2, XCircle } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import TraceTimeline from '../../components/Admin/TraceTimeline.jsx'
import { getTraceDetail } from '../../services/adminTrace.js'

export default function AdminTraceDetail() {
  const setActiveView = useAppStore(state => state.setActiveView)
  const [trace, setTrace] = useState(null)
  const [loading, setLoading] = useState(true)
  const traceId = sessionStorage.getItem('currentTraceId')

  useEffect(() => {
    if (traceId) {
      loadTraceDetail()
    }
  }, [traceId])

  const loadTraceDetail = async () => {
    try {
      setLoading(true)
      const data = await getTraceDetail(traceId)
      setTrace(data)
    } catch (error) {
      console.error('加载轨迹详情失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    sessionStorage.removeItem('currentTraceId')
    setActiveView('admin-trace-list')
  }

  const formatTime = (timeStr) => {
    if (!timeStr) return '-'
    return new Date(timeStr).toLocaleString('zh-CN')
  }

  if (!traceId) {
    return (
      <div className="p-6">
        <div className="text-center py-12">
          <p className="text-[var(--text-muted)] mb-4">未选择要查看的轨迹</p>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-[var(--brand-soft)] text-white rounded-lg text-sm hover:bg-[var(--brand-soft)]/90 transition-colors"
          >
            返回轨迹列表
          </button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-[var(--bg-sidebar)]/50 rounded" />
          <div className="h-32 bg-[var(--bg-sidebar)]/50 rounded-xl" />
          <div className="space-y-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="h-24 bg-[var(--bg-sidebar)]/50 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      {/* 头部导航 */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={handleBack}
          className="p-2 hover:bg-[var(--bg-sidebar)] rounded-lg transition-colors"
          title="返回列表"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-bold">轨迹详情 #{traceId}</h1>
        <div className={`ml-auto px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1.5 ${
          trace.success ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'
        }`}>
          {trace.success ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
          {trace.success ? '执行成功' : '执行失败'}
        </div>
      </div>

      {/* 基础信息卡片 */}
      <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] p-5 mb-6">
        <h2 className="text-lg font-medium mb-4">基础信息</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">会话ID</p>
            <p className="font-mono text-sm">{trace.session_id}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">用户ID</p>
            <div className="flex items-center gap-1.5">
              <User size={14} className="text-[var(--text-muted)]" />
              <p className="text-sm">{trace.user_id || '-'}</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">项目ID</p>
            <div className="flex items-center gap-1.5">
              <Hash size={14} className="text-[var(--text-muted)]" />
              <p className="text-sm">{trace.project_id || '-'}</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">创建时间</p>
            <div className="flex items-center gap-1.5">
              <Calendar size={14} className="text-[var(--text-muted)]" />
              <p className="text-sm">{formatTime(trace.created_at)}</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">模型</p>
            <p className="text-sm">{trace.model}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">迭代次数</p>
            <p className="text-sm">{trace.iterations} 轮</p>
          </div>
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">执行耗时</p>
            <div className="flex items-center gap-1.5">
              <Clock size={14} className="text-[var(--text-muted)]" />
              <p className="text-sm">{trace.cost_time.toFixed(2)} 秒</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-[var(--text-muted)] mb-1">工具调用次数</p>
            <p className="text-sm">{trace.tool_calls?.length || 0} 次</p>
          </div>
        </div>

        {/* 模型参数 */}
        <div className="mt-6 pt-4 border-t border-[var(--border-soft)]">
          <h3 className="text-sm font-medium mb-3">模型参数</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-[var(--text-muted)] mb-1">Temperature</p>
              <p className="text-sm">{trace.temperature}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)] mb-1">Max Tokens</p>
              <p className="text-sm">{trace.max_tokens}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)] mb-1">Top P</p>
              <p className="text-sm">{trace.top_p}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 推理链路时间线 */}
      <TraceTimeline trace={trace} />
    </div>
  )
}
