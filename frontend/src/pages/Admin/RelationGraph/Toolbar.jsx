import { Search, Filter, Download, Layers, Zap } from 'lucide-react'

const Toolbar = ({ filters, onFilterChange, onExport, onRefresh }) => {
  const { nodeTypes, minUsage, minSuccessRate, searchKeyword } = filters

  const handleTypeToggle = (type) => {
    const newTypes = nodeTypes.includes(type)
      ? nodeTypes.filter(t => t !== type)
      : [...nodeTypes, type]
    onFilterChange({ nodeTypes: newTypes })
  }

  return (
    <div className="graph-toolbar">
      <div className="space-y-2">
        <div className="text-sm font-semibold flex items-center gap-2">
          <Search size={14} />
          搜索
        </div>
        <input
          type="text"
          placeholder="搜索名称/描述"
          value={searchKeyword}
          onChange={(e) => onFilterChange({ searchKeyword: e.target.value })}
          className="w-full px-2 py-1 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="border-t pt-2 space-y-2">
        <div className="text-sm font-semibold flex items-center gap-2">
          <Layers size={14} />
          节点类型
        </div>
        <div className="space-y-1">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={nodeTypes.includes('strategy')}
              onChange={() => handleTypeToggle('strategy')}
              className="cursor-pointer"
            />
            <span className="w-3 h-3 rounded-full bg-blue-500" />
            策略
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={nodeTypes.includes('template')}
              onChange={() => handleTypeToggle('template')}
              className="cursor-pointer"
            />
            <span className="w-3 h-3 rounded-full bg-green-500" />
            模板
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={nodeTypes.includes('factor')}
              onChange={() => handleTypeToggle('factor')}
              className="cursor-pointer"
            />
            <span className="w-3 h-3 rounded-full bg-orange-500" />
            因子
          </label>
        </div>
      </div>

      <div className="border-t pt-2 space-y-2">
        <div className="text-sm font-semibold flex items-center gap-2">
          <Filter size={14} />
          筛选条件
        </div>
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-xs text-gray-500">最小使用次数: {minUsage}</label>
            <input
              type="range"
              min="0"
              max="500"
              step="10"
              value={minUsage}
              onChange={(e) => onFilterChange({ minUsage: parseInt(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-500">
              最低成功率: {(minSuccessRate * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minSuccessRate}
              onChange={(e) => onFilterChange({ minSuccessRate: parseFloat(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="border-t pt-2 flex gap-2">
        <button
          onClick={onExport}
          className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-gray-100 rounded text-sm hover:bg-gray-200 transition"
          title="导出图片"
        >
          <Download size={14} />
          导出
        </button>
        <button
          onClick={onRefresh}
          className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-gray-100 rounded text-sm hover:bg-gray-200 transition"
          title="刷新数据"
        >
          <Zap size={14} />
          刷新
        </button>
      </div>
    </div>
  )
}

export default Toolbar
