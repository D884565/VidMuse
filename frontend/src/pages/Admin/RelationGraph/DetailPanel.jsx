import { X, ExternalLink } from 'lucide-react'
import { NODE_TYPE_MAP } from './config'

const DetailPanel = ({ item, onClose }) => {
  const { type, data } = item

  // 格式化数值
  const formatValue = (key, value) => {
    if (key.includes('rate') && typeof value === 'number') {
      return `${(value * 100).toFixed(1)}%`
    }
    if (key === 'tags' && Array.isArray(value)) {
      return value.join(', ')
    }
    if (key === 'applicable_scenarios' && Array.isArray(value)) {
      return value.join(', ')
    }
    if (typeof value === 'boolean') {
      return value ? '是' : '否'
    }
    return value ?? '-'
  }

  // 获取详情项列表
  const getDetailItems = () => {
    if (type === 'node') {
      const nodeData = data.data || {}
      const baseItems = [
        { label: '类型', value: NODE_TYPE_MAP[data.type]?.label || data.type },
        { label: '名称', value: data.name },
        { label: 'ID', value: nodeData.id || '-' },
        { label: '使用次数', value: nodeData.usage_count },
      ]

      if (nodeData.success_rate !== undefined) {
        baseItems.push({ label: '成功率', value: nodeData.success_rate })
      }
      if (nodeData.popularity !== undefined) {
        baseItems.push({ label: '流行度', value: (nodeData.popularity * 100).toFixed(0) + '%' })
      }
      if (nodeData.version) {
        baseItems.push({ label: '版本', value: nodeData.version })
      }
      if (nodeData.factor_type) {
        const typeMap = {
          'content_structure': '内容结构',
          'product_expression': '产品表达',
          'user_operation': '用户行为',
        }
        baseItems.push({ label: '因子类型', value: typeMap[nodeData.factor_type] || nodeData.factor_type })
      }
      if (nodeData.description) {
        baseItems.push({ label: '描述', value: nodeData.description })
      }
      if (nodeData.tags?.length) {
        baseItems.push({ label: '标签', value: nodeData.tags })
      }
      if (nodeData.applicable_scenarios?.length) {
        baseItems.push({ label: '适用场景', value: nodeData.applicable_scenarios })
      }

      return baseItems
    } else { // edge
      const edgeData = data.data || {}
      return [
        { label: '关系类型', value: data.type === 'strategy-template' ? '策略→模板' : '模板→因子' },
        { label: '源节点', value: data.source },
        { label: '目标节点', value: data.target },
        { label: '关联类型', value: data.label },
        { label: '关联强度', value: data.value.toFixed(1) },
        ...(edgeData.usage_count !== undefined ? [{ label: '关联使用次数', value: edgeData.usage_count }] : []),
        ...(edgeData.success_rate !== undefined ? [{ label: '关联成功率', value: edgeData.success_rate }] : []),
        ...(edgeData.weight !== undefined ? [{ label: '权重', value: edgeData.weight }] : []),
      ]
    }
  }

  // 获取跳转链接
  const getJumpLink = () => {
    if (type !== 'node') return null

    const nodeData = data.data || {}
    switch (data.type) {
      case 'strategy':
        return `/admin/inspiration?tab=strategies&id=${nodeData.id}`
      case 'template':
        return `/admin/inspiration?tab=templates&id=${nodeData.id}`
      case 'factor':
        return `/admin/inspiration?tab=factors&id=${nodeData.id}`
      default:
        return null
    }
  }

  const detailItems = getDetailItems()
  const jumpLink = getJumpLink()

  return (
    <div className="graph-detail-panel">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-base">
          {type === 'node' ? '节点详情' : '关系详情'}
        </h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded transition"
        >
          <X size={16} />
        </button>
      </div>

      <div className="space-y-3">
        {detailItems.map((item, index) => (
          <div key={index} className="node-detail-item">
            <div className="node-detail-label">{item.label}</div>
            <div className="node-detail-value break-words">
              {formatValue(item.label, item.value)}
            </div>
          </div>
        ))}
      </div>

      {jumpLink && (
        <div className="mt-4 pt-4 border-t">
          <a
            href={jumpLink}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2 bg-blue-50 text-blue-600 rounded text-sm hover:bg-blue-100 transition"
          >
            <ExternalLink size={14} />
            跳转到管理页面
          </a>
        </div>
      )}
    </div>
  )
}

export default DetailPanel
