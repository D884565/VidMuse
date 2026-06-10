import G6 from '@antv/g6'

// 图谱全局配置
export const GRAPH_CONFIG = {
  container: 'graph-container',
  width: 1200,
  height: 800,
  modes: {
    default: [
      'drag-canvas',
      'zoom-canvas',
      'drag-node',
      {
        type: 'tooltip',
        formatText: (model) => {
          return `
            <div class="graph-tooltip">
              <div class="font-bold">${model.name}</div>
              <div class="text-sm text-gray-500">${getTypeLabel(model.nodeType || model.type)}</div>
              ${model.data?.usage_count !== undefined ? `<div class="text-xs">使用次数: ${model.data.usage_count}</div>` : ''}
              ${model.data?.success_rate !== undefined ? `<div class="text-xs">成功率: ${(model.data.success_rate * 100).toFixed(1)}%</div>` : ''}
            </div>
          `
        }
      }
    ]
  },
  layout: {
    type: 'force',
    preventOverlap: true,
    nodeSize: (node) => node.size || 30,
    linkDistance: 150,
    nodeStrength: -50,
    edgeStrength: 0.5
  },
  defaultNode: {
    type: 'circle',
    style: {
      lineWidth: 2,
      stroke: '#fff'
    },
    labelCfg: {
      style: {
        fill: '#333',
        fontSize: 12
      }
    }
  },
  defaultEdge: {
    type: 'cubic-horizontal',
    style: {
      opacity: 0.6,
      endArrow: {
        path: G6.Arrow.triangle(8, 10, 0),
        fill: '#aaa'
      }
    },
    labelCfg: {
      autoRotate: true,
      style: {
        fill: '#666',
        fontSize: 10,
        background: {
          fill: '#fff',
          padding: [2, 4, 2, 4],
          radius: 2
        }
      }
    }
  },
  nodeStateStyles: {
    highlight: {
      stroke: '#ff4d4f',
      lineWidth: 4
    },
    related: {
      stroke: '#1890ff',
      lineWidth: 3,
      opacity: 0.8
    }
  },
  edgeStateStyles: {
    highlight: {
      stroke: '#ff4d4f',
      lineWidth: 4,
      opacity: 1
    }
  }
}

// 节点类型映射
export const NODE_TYPE_MAP = {
  strategy: { label: '策略', color: '#1890ff' },
  template: { label: '模板', color: '#52c41a' },
  factor: { label: '因子', color: '#fa8c16' }
}

export function getTypeLabel(type) {
  return NODE_TYPE_MAP[type]?.label || type
}

// 边样式映射
export const EDGE_STYLE_MAP = {
  'strategy-template': { color: '#1890ff', style: 'solid' },
  'template-factor': {
    1: { color: '#f5222d', style: 'solid', label: '必填' },
    2: { color: '#faad14', style: 'dashed', label: '可选' }
  }
}
