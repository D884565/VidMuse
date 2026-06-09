import { useState, useEffect, useRef } from 'react'
import G6 from '@antv/g6'
import { RefreshCw } from 'lucide-react'
import PageContainer from '../../../components/Admin/Layout/PageContainer'
import Toolbar from './Toolbar'
import DetailPanel from './DetailPanel'
import { GRAPH_CONFIG } from './config'
import { getRelationGraph } from '../../../services/admin'
import './style.css'

const RelationGraph = () => {
  const graphRef = useRef(null)
  const containerRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] })
  const [selectedItem, setSelectedItem] = useState(null)
  const [filters, setFilters] = useState({
    nodeTypes: ['strategy', 'template', 'factor'],
    minUsage: 0,
    minSuccessRate: 0,
    searchKeyword: ''
  })

  // 初始化图谱
  useEffect(() => {
    if (!containerRef.current) return

    try {
      const graph = new G6.Graph({
        ...GRAPH_CONFIG,
        container: containerRef.current,
        width: containerRef.current.offsetWidth,
        height: containerRef.current.offsetHeight
      })

      // 节点点击事件
      graph.on('node:click', (e) => {
        const node = e.item
        const model = node.getModel()
        setSelectedItem({ type: 'node', data: model })

        // 高亮关联节点和边
        highlightRelated(node, graph)
      })

      // 边点击事件
      graph.on('edge:click', (e) => {
        const edge = e.item
        const model = edge.getModel()
        setSelectedItem({ type: 'edge', data: model })
      })

      // 画布点击事件
      graph.on('canvas:click', () => {
        setSelectedItem(null)
        clearHighlight(graph)
      })

      // 渲染空数据
      graph.changeData({ nodes: [], edges: [] })

      graphRef.current = graph

      // 响应式调整
      const handleResize = () => {
        if (containerRef.current && graph) {
          graph.changeSize(
            containerRef.current.offsetWidth,
            containerRef.current.offsetHeight
          )
        }
      }
      window.addEventListener('resize', handleResize)

      return () => {
        window.removeEventListener('resize', handleResize)
        if (graph) {
          graph.destroy()
        }
      }
    } catch (error) {
      console.error('G6初始化失败:', error)
      alert('图谱初始化失败，请刷新页面重试')
    }
  }, [])

  // 加载数据
  const loadGraphData = async () => {
    setLoading(true)
    try {
      const params = {
        min_usage: filters.minUsage || undefined,
        min_success_rate: filters.minSuccessRate > 0 ? filters.minSuccessRate : undefined
      }
      const res = await getRelationGraph(params)
      const data = res.data || { nodes: [], edges: [] }
      setGraphData(data)

      // 应用筛选后渲染
      renderGraph(data)
    } catch (error) {
      console.error('加载图谱数据失败:', error)
      alert('加载图谱数据失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  // 渲染图谱
  const renderGraph = (data) => {
    if (!graphRef.current || !data) return

    // 应用筛选
    const filteredData = applyFilters(data)
    if (!filteredData) return

    // 转换数据格式适配G6
    const g6Data = {
      nodes: (filteredData.nodes || []).map(node => ({
        id: node.id,
        type: 'circle',
        size: node.size || 30,
        color: node.color || '#999',
        style: { fill: node.color || '#999' },
        label: node.name?.length > 8 ? node.name.slice(0, 6) + '...' : node.name || '',
        ...node
      })),
      edges: (filteredData.edges || []).map(edge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label || '',
        style: {
          stroke: edge.color || '#999',
          lineDash: edge.style === 'dashed' ? [5, 5] : edge.style === 'dotted' ? [2, 2] : [],
          lineWidth: edge.value || 1
        },
        ...edge
      }))
    }

    graphRef.current.changeData(g6Data)
  }

  // 应用筛选
  const applyFilters = (data) => {
    if (!data) return { nodes: [], edges: [] }

    let nodes = data.nodes || []
    let edges = data.edges || []

    // 按节点类型筛选
    nodes = nodes.filter(node => filters.nodeTypes.includes(node.type))

    // 按关键词筛选
    if (filters.searchKeyword) {
      const keyword = filters.searchKeyword.toLowerCase()
      nodes = nodes.filter(node =>
        node.name?.toLowerCase().includes(keyword) ||
        node.data?.description?.toLowerCase().includes(keyword)
      )
    }

    // 按使用量筛选
    if (filters.minUsage > 0) {
      nodes = nodes.filter(node =>
        (node.data?.usage_count || 0) >= filters.minUsage
      )
    }

    // 按成功率筛选
    if (filters.minSuccessRate > 0) {
      nodes = nodes.filter(node =>
        (node.data?.success_rate || 0) >= filters.minSuccessRate
      )
    }

    // 过滤边，只保留两端都存在的边
    const nodeIds = new Set(nodes.map(n => n.id))
    edges = edges.filter(edge =>
      nodeIds.has(edge.source) && nodeIds.has(edge.target)
    )

    return { nodes, edges }
  }

  // 高亮关联节点
  const highlightRelated = (node, graph) => {
    const nodeId = node.getID()
    const allNodes = graph.getNodes()
    const allEdges = graph.getEdges()

    // 先清除所有高亮
    clearHighlight(graph)

    // 高亮当前节点
    graph.setItemState(node, 'highlight', true)

    // 查找所有关联的边和节点
    const relatedEdges = allEdges.filter(edge =>
      edge.getSource().getID() === nodeId || edge.getTarget().getID() === nodeId
    )

    const relatedNodeIds = new Set()
    relatedEdges.forEach(edge => {
      graph.setItemState(edge, 'highlight', true)
      const sourceId = edge.getSource().getID()
      const targetId = edge.getTarget().getID()
      if (sourceId !== nodeId) relatedNodeIds.add(sourceId)
      if (targetId !== nodeId) relatedNodeIds.add(targetId)
    })

    // 高亮关联节点
    allNodes.forEach(n => {
      if (relatedNodeIds.has(n.getID())) {
        graph.setItemState(n, 'related', true)
      }
    })
  }

  // 清除所有高亮
  const clearHighlight = (graph) => {
    graph.getNodes().forEach(node => {
      graph.clearItemStates(node)
    })
    graph.getEdges().forEach(edge => {
      graph.clearItemStates(edge)
    })
  }

  // 处理筛选变化
  const handleFilterChange = (newFilters) => {
    setFilters(prev => ({ ...prev, ...newFilters }))
    renderGraph(graphData)
  }

  // 导出图谱
  const handleExport = () => {
    if (!graphRef.current) return
    const dataURL = graphRef.current.toDataURL('image/png')
    const link = document.createElement('a')
    link.download = `relation-graph-${new Date().toISOString().slice(0, 10)}.png`
    link.href = dataURL
    link.click()
  }

  // 初始化加载
  useEffect(() => {
    loadGraphData()
  }, [])

  return (
    <PageContainer title="灵感模板关系图谱">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm text-gray-500">
          共 {graphData?.nodes?.length || 0} 个节点，{graphData?.edges?.length || 0} 条关系
        </div>
        <button
          onClick={loadGraphData}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition disabled:bg-blue-300"
          disabled={loading}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新数据
        </button>
      </div>

      <div className="relative">
        <div ref={containerRef} className="graph-container" />

        <Toolbar
          filters={filters}
          onFilterChange={handleFilterChange}
          onExport={handleExport}
          onRefresh={loadGraphData}
        />

        {selectedItem && (
          <DetailPanel
            item={selectedItem}
            onClose={() => setSelectedItem(null)}
          />
        )}
      </div>
    </PageContainer>
  )
}

export default RelationGraph
