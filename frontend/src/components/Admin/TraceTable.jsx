import { Eye, CheckCircle2, XCircle } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

/**
 * 轨迹表格组件
 * @param {Array} traces 轨迹列表数据
 * @param {Function} onViewDetail 查看详情回调
 * @param {boolean} loading 加载状态
 */
export default function TraceTable({ traces, onViewDetail, loading }) {
  const setActiveView = useAppStore(state => state.setActiveView)

  const formatTime = (timeStr) => {
    if (!timeStr) return '-'
    return new Date(timeStr).toLocaleString('zh-CN')
  }

  const truncateText = (text, maxLength = 50) => {
    if (!text) return '-'
    return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
  }

  if (loading) {
    return (
      <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] overflow-hidden">
        <div className="animate-pulse">
          <div className="h-12 bg-[var(--bg-sidebar)]/50 border-b border-[var(--border-soft)]" />
          {[1,2,3,4,5].map(i => (
            <div key={i} className="h-16 bg-[var(--bg-sidebar)]/50 border-b border-[var(--border-soft)]" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-[var(--bg)]">
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">ID</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">会话ID</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">用户输入</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">模型</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">迭代次数</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">耗时</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">状态</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">创建时间</th>
              <th className="text-left p-4 text-sm font-medium text-[var(--text-muted)] border-b border-[var(--border-soft)]">操作</th>
            </tr>
          </thead>
          <tbody>
            {traces?.length === 0 ? (
              <tr>
                <td colSpan={9} className="p-8 text-center text-[var(--text-muted)]">
                  暂无数据
                </td>
              </tr>
            ) : (
              traces?.map((trace) => (
                <tr key={trace.id} className="border-b border-[var(--border-soft)] hover:bg-[var(--bg)] transition-colors">
                  <td className="p-4 text-sm">{trace.id}</td>
                  <td className="p-4 text-sm font-mono text-xs">{trace.session_id}</td>
                  <td className="p-4 text-sm max-w-[300px]">
                    {truncateText(trace.user_input)}
                  </td>
                  <td className="p-4 text-sm">{trace.model}</td>
                  <td className="p-4 text-sm">{trace.iterations}</td>
                  <td className="p-4 text-sm">{trace.cost_time.toFixed(2)}s</td>
                  <td className="p-4 text-sm">
                    <div className="flex items-center gap-1.5">
                      {trace.success ? (
                        <>
                          <CheckCircle2 size={14} className="text-green-500" />
                          <span className="text-green-500">成功</span>
                        </>
                      ) : (
                        <>
                          <XCircle size={14} className="text-red-500" />
                          <span className="text-red-500">失败</span>
                        </>
                      )}
                    </div>
                  </td>
                  <td className="p-4 text-sm whitespace-nowrap">
                    {formatTime(trace.created_at)}
                  </td>
                  <td className="p-4 text-sm">
                    <button
                      onClick={() => {
                        // 存储当前选中的trace ID到store或者全局
                        sessionStorage.setItem('currentTraceId', trace.id)
                        setActiveView('admin-trace-detail')
                        onViewDetail?.(trace)
                      }}
                      className="flex items-center gap-1 text-[var(--brand-soft)] hover:text-[var(--brand-soft)]/80 transition-colors"
                    >
                      <Eye size={14} />
                      <span>详情</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
