import { useState } from 'react'
import { Search, Calendar, X } from 'lucide-react'

/**
 * 轨迹筛选组件
 * @param {Object} filters 当前筛选条件
 * @param {Function} onFilterChange 筛选条件变化回调
 * @param {Function} onSearch 搜索回调
 */
export default function TraceFilter({ filters, onFilterChange, onSearch }) {
  const [isExpanded, setIsExpanded] = useState(false)

  const handleChange = (key, value) => {
    onFilterChange({ ...filters, [key]: value })
  }

  const handleReset = () => {
    onFilterChange({
      session_id: '',
      user_id: '',
      project_id: '',
      model: '',
      success: '',
      start_time: '',
      end_time: '',
      keyword: ''
    })
    onSearch()
  }

  return (
    <div className="bg-[var(--bg-sidebar)] rounded-xl border border-[var(--border-soft)] p-4 mb-4">
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {/* 关键词搜索 */}
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="搜索用户输入/回答..."
            value={filters.keyword || ''}
            onChange={(e) => handleChange('keyword', e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
            onKeyDown={(e) => e.key === 'Enter' && onSearch()}
          />
        </div>

        {/* 执行结果 */}
        <select
          value={filters.success ?? ''}
          onChange={(e) => handleChange('success', e.target.value === '' ? undefined : e.target.value === 'true')}
          className="bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
        >
          <option value="">全部状态</option>
          <option value="true">成功</option>
          <option value="false">失败</option>
        </select>

        {/* 模型 */}
        <input
          type="text"
          placeholder="模型名称"
          value={filters.model || ''}
          onChange={(e) => handleChange('model', e.target.value)}
          className="bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
        />

        {/* 展开/收起按钮 */}
        <div className="flex gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex-1 px-3 py-2 border border-[var(--border-soft)] rounded-lg text-sm hover:bg-[var(--bg)] transition-colors"
          >
            {isExpanded ? '收起筛选' : '更多筛选'}
          </button>
          <button
            onClick={handleReset}
            className="px-3 py-2 border border-[var(--border-soft)] rounded-lg text-sm hover:bg-[var(--bg)] transition-colors"
            title="重置筛选"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* 展开的筛选条件 */}
      {isExpanded && (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-4 pt-4 border-t border-[var(--border-soft)]">
          <input
            type="text"
            placeholder="会话ID"
            value={filters.session_id || ''}
            onChange={(e) => handleChange('session_id', e.target.value)}
            className="bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
          />
          <input
            type="number"
            placeholder="用户ID"
            value={filters.user_id || ''}
            onChange={(e) => handleChange('user_id', e.target.value ? Number(e.target.value) : '')}
            className="bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
          />
          <input
            type="number"
            placeholder="项目ID"
            value={filters.project_id || ''}
            onChange={(e) => handleChange('project_id', e.target.value ? Number(e.target.value) : '')}
            className="bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
          />
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="datetime-local"
                placeholder="开始时间"
                value={filters.start_time ? new Date(filters.start_time).toISOString().slice(0, 16) : ''}
                onChange={(e) => handleChange('start_time', e.target.value ? new Date(e.target.value).toISOString() : '')}
                className="w-full pl-9 pr-3 py-2 bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
              />
            </div>
            <div className="relative flex-1">
              <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="datetime-local"
                placeholder="结束时间"
                value={filters.end_time ? new Date(filters.end_time).toISOString().slice(0, 16) : ''}
                onChange={(e) => handleChange('end_time', e.target.value ? new Date(e.target.value).toISOString() : '')}
                className="w-full pl-9 pr-3 py-2 bg-[var(--bg)] border border-[var(--border-soft)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-soft)]/20 focus:border-[var(--brand-soft)]"
              />
            </div>
          </div>
        </div>
      )}

      {/* 搜索按钮 */}
      <div className="flex justify-end mt-4">
        <button
          onClick={onSearch}
          className="px-4 py-2 bg-[var(--brand-soft)] text-white rounded-lg text-sm hover:bg-[var(--brand-soft)]/90 transition-colors"
        >
          搜索
        </button>
      </div>
    </div>
  )
}
