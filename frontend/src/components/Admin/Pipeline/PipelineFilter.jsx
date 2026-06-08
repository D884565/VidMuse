import { useState } from 'react'
import { Search, Filter, Calendar, X } from 'lucide-react'
import Button from '@/components/Button/Button'

// 简单的Input组件
const Input = ({ prefix, placeholder, value, onChange, className = '' }) => (
  <div className={`relative flex items-center ${className}`}>
    {prefix && <div className="absolute left-3">{prefix}</div>}
    <input
      type="text"
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      className={`w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${prefix ? 'pl-10' : ''}`}
    />
  </div>
)

// 简单的Select组件
const Select = ({ options, value, onChange, placeholder }) => (
  <select
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
  >
    {options.map(option => (
      <option key={option.value} value={option.value}>
        {option.label}
      </option>
    ))}
  </select>
)

// 简单的DatePicker组件
const DatePicker = ({ placeholder, value, onChange }) => (
  <input
    type="date"
    placeholder={placeholder}
    value={value ? value.toISOString().split('T')[0] : ''}
    onChange={(e) => onChange(e.target.value ? new Date(e.target.value) : null)}
    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
  />
)

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待执行' },
  { value: 'running', label: '执行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' }
]

const typeOptions = [
  { value: '', label: '全部类型' },
  { value: 'video', label: '视频处理' },
  { value: 'product', label: '商品处理' },
  { value: 'video_overall', label: '视频综合' }
]

export default function PipelineFilter({ filters, onFilterChange, onReset }) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleChange = (key, value) => {
    onFilterChange({ ...filters, [key]: value })
  }

  return (
    <div className="bg-white p-4 rounded-lg shadow-sm mb-4">
      <div className="flex items-center gap-4 flex-wrap">
        {/* 关键词搜索 */}
        <div className="flex-1 min-w-[200px]">
          <Input
            prefix={<Search className="w-4 h-4 text-gray-400" />}
            placeholder="搜索流水线名称/ID"
            value={filters.keyword || ''}
            onChange={(e) => handleChange('keyword', e.target.value)}
            className="w-full"
          />
        </div>

        {/* 状态筛选 */}
        <div className="w-[150px]">
          <Select
            options={statusOptions}
            value={filters.status || ''}
            onChange={(value) => handleChange('status', value)}
            placeholder="状态"
          />
        </div>

        {/* 类型筛选 */}
        <div className="w-[150px]">
          <Select
            options={typeOptions}
            value={filters.pipeline_type || ''}
            onChange={(value) => handleChange('pipeline_type', value)}
            placeholder="类型"
          />
        </div>

        {/* 高级筛选开关 */}
        <Button
          type="text"
          icon={<Filter className="w-4 h-4" />}
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? '收起筛选' : '高级筛选'}
        </Button>

        {/* 重置按钮 */}
        <Button
          type="text"
          icon={<X className="w-4 h-4" />}
          onClick={onReset}
        >
          重置
        </Button>
      </div>

      {/* 高级筛选 */}
      {showAdvanced && (
        <div className="mt-4 pt-4 border-t border-gray-100 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">时间范围:</span>
            <DatePicker
              placeholder="开始时间"
              value={filters.start_time ? new Date(filters.start_time * 1000) : null}
              onChange={(date) => handleChange('start_time', date ? Math.floor(date.getTime() / 1000) : null)}
            />
            <span className="text-gray-400">~</span>
            <DatePicker
              placeholder="结束时间"
              value={filters.end_time ? new Date(filters.end_time * 1000) : null}
              onChange={(date) => handleChange('end_time', date ? Math.floor(date.getTime() / 1000) : null)}
            />
          </div>
        </div>
      )}
    </div>
  )
}
