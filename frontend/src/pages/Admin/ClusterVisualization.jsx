import { useState, useEffect } from 'react'
import {
  BarChart3,
  PieChart,
  Network,
  RefreshCw,
  Download,
  Info,
  ChevronDown,
  ChevronRight
} from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import { Card, Tabs, Select, Button, Table, Modal, message, Tag, Space, Progress } from 'antd'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Cell as BarCell
} from 'recharts'
import {
  getClusterOverview,
  getClusterDetail
} from '../../services/admin'

const { TabPane } = Tabs
const { Option } = Select

// 颜色方案
const CLUSTER_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
  '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52B788',
  '#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6',
  '#1ABC9C', '#E67E22', '#34495E', '#95A5A6', '#27AE60'
]

export default function ClusterVisualization() {
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [overview, setOverview] = useState(null)
  const [clusters, setClusters] = useState([])
  const [selectedCluster, setSelectedCluster] = useState(null)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [expandedClusters, setExpandedClusters] = useState(new Set())

  // 加载数据
  const loadData = async () => {
    setLoading(true)
    try {
      const overviewData = await getClusterOverview()
      setOverview(overviewData.data)
      setClusters(overviewData.data?.clusters || [])
    } catch (error) {
      message.error('加载聚类数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // 查看簇详情
  const viewClusterDetail = async (clusterId) => {
    try {
      const detail = await getClusterDetail(clusterId)
      setSelectedCluster(detail.data)
      setDetailModalVisible(true)
    } catch (error) {
      message.error('加载簇详情失败')
    }
  }

  // 切换簇展开/收起
  const toggleClusterExpand = (clusterId) => {
    const newExpanded = new Set(expandedClusters)
    if (newExpanded.has(clusterId)) {
      newExpanded.delete(clusterId)
    } else {
      newExpanded.add(clusterId)
    }
    setExpandedClusters(newExpanded)
  }

  // 生成散点图数据（降维后的向量）
  const getScatterData = () => {
    if (!overview?.visualization_data) return []
    return overview.visualization_data.points || []
  }

  // 生成饼图数据
  const getPieData = () => {
    return clusters.map(cluster => ({
      name: `簇 ${cluster.cluster_id}`,
      value: cluster.sample_count,
      cluster_id: cluster.cluster_id
    }))
  }

  // 生成柱状图数据
  const getBarData = () => {
    return clusters.map(cluster => ({
      name: `簇 ${cluster.cluster_id}`,
      count: cluster.sample_count,
      factor_count: cluster.factor_count || 0,
      cluster_id: cluster.cluster_id
    })).sort((a, b) => b.count - a.count)
  }

  // 簇列表列配置
  const clusterColumns = [
    {
      key: 'expand',
      title: '',
      width: 50,
      render: (_, record) => (
        <Button
          type="text"
          icon={expandedClusters.has(record.cluster_id) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          onClick={() => toggleClusterExpand(record.cluster_id)}
        />
      )
    },
    {
      key: 'cluster_id',
      dataIndex: 'cluster_id',
      title: '簇ID',
      width: 80,
      render: (id) => id?.toString() || '-'
    },
    {
      key: 'sample_count',
      title: '样本数',
      width: 100,
      render: (count) => typeof count === 'number' ? <Tag color="blue">{count}</Tag> : '-'
    },
    {
      key: 'factor_count',
      title: '提取因子数',
      width: 100,
      render: (count) => typeof count === 'number' ? <Tag color="green">{count}</Tag> : '-'
    },
    {
      key: 'avg_similarity',
      title: '平均相似度',
      width: 120,
      render: (val) => typeof val === 'number' ? (
        <Progress
          percent={Math.round(val * 100)}
          size="small"
          strokeColor="#52c41a"
        />
      ) : '-'
    },
    {
      key: 'dominant_type',
      title: '主导类型',
      width: 120,
      render: (type) => {
        if (!type || typeof type !== 'string') return '-'
        const typeMap = {
          'content_structure': <Tag color="blue">内容结构</Tag>,
          'product_expression': <Tag color="orange">产品表达</Tag>,
          'user_operation': <Tag color="purple">用户运营</Tag>,
          'mixed': <Tag color="cyan">混合</Tag>
        }
        return typeMap[type] || <Tag>{type.toString()}</Tag>
      }
    },
    {
      key: 'actions',
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<Info size={14} />}
            onClick={() => viewClusterDetail(record.cluster_id)}
          >
            详情
          </Button>
        </Space>
      )
    }
  ]

  return (
    <PageContainer
      title="向量聚类可视化"
      extra={
        <Space>
          <Button
            icon={<RefreshCw size={16} />}
            onClick={loadData}
            loading={loading}
          >
            刷新
          </Button>
        </Space>
      }
    >
      {/* 统计卡片 */}
      {overview && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <Card className="shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm mb-1">总向量数</p>
                <p className="text-2xl font-bold">{overview.total_vectors}</p>
              </div>
              <div className="bg-blue-100 p-3 rounded-full">
                <BarChart3 className="text-blue-600" size={24} />
              </div>
            </div>
            <div className="mt-4 text-xs text-gray-500">
              slice: {overview.slice_count} / video: {overview.video_count}
            </div>
          </Card>

          <Card className="shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm mb-1">簇数量</p>
                <p className="text-2xl font-bold">{overview.total_clusters}</p>
              </div>
              <div className="bg-green-100 p-3 rounded-full">
                <PieChart className="text-green-600" size={24} />
              </div>
            </div>
            <div className="mt-4 text-xs text-gray-500">
              slice簇: {overview.slice_clusters} / video簇: {overview.video_clusters}
            </div>
          </Card>

          <Card className="shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm mb-1">提取因子</p>
                <p className="text-2xl font-bold">{overview.total_factors}</p>
              </div>
              <div className="bg-purple-100 p-3 rounded-full">
                <Network className="text-purple-600" size={24} />
              </div>
            </div>
            <div className="mt-4 text-xs text-gray-500">
              生成策略: {overview.total_strategies} 个
            </div>
          </Card>

          <Card className="shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm mb-1">聚类质量</p>
                <p className="text-2xl font-bold">{(overview.avg_silhouette * 100).toFixed(1)}%</p>
              </div>
              <div className="bg-orange-100 p-3 rounded-full">
                <BarChart3 className="text-orange-600" size={24} />
              </div>
            </div>
            <div className="mt-4">
              <Progress
                percent={(overview.avg_silhouette * 100).toFixed(0)}
                size="small"
                strokeColor={overview.avg_silhouette > 0.7 ? '#52c41a' : overview.avg_silhouette > 0.5 ? '#faad14' : '#ff4d4f'}
              />
            </div>
          </Card>
        </div>
      )}


      {/* 主内容 */}
      <Tabs activeKey={activeTab} onChange={setActiveTab} className="mb-6">
        <TabPane tab="概览" key="overview">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 向量分布散点图 */}
            <Card title="向量分布可视化 (t-SNE降维)" className="shadow-sm">
              {getScatterData().length > 0 ? (
                <ResponsiveContainer width="100%" height={400}>
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="x" name="X" />
                    <YAxis type="number" dataKey="y" name="Y" />
                    <ZAxis type="number" dataKey="cluster_id" range={[60, 400]} name="簇ID" />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                    <Legend />
                    <Scatter
                      name="向量点"
                      data={getScatterData()}
                      fillOpacity={0.8}
                    >
                      {getScatterData().map((entry, index) => {
                        // 处理cluster_id，确保是数字
                        let clusterId = entry.cluster_id;
                        if (typeof clusterId === 'string') {
                          // 提取数字部分或简单哈希
                          const match = clusterId.match(/\d+/);
                          clusterId = match ? parseInt(match[0]) : index;
                        }
                        return (
                          <Cell
                            key={`cell-${index}`}
                            fill={CLUSTER_COLORS[Math.abs(clusterId) % CLUSTER_COLORS.length]}
                          />
                        );
                      })}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[400px] flex items-center justify-center text-gray-400">
                  <p>暂无可视化数据，请先点击"运行聚类分析"</p>
                </div>
              )}
            </Card>

            {/* 簇大小分布饼图 */}
            <Card title="簇大小分布" className="shadow-sm">
              {getPieData().length > 0 ? (
                <ResponsiveContainer width="100%" height={400}>
                  <RechartsPieChart>
                    <Pie
                      data={getPieData()}
                      cx="50%"
                      cy="50%"
                      labelLine={true}
                      outerRadius={130}
                      fill="#8884d8"
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {getPieData().map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={CLUSTER_COLORS[index % CLUSTER_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </RechartsPieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[400px] flex items-center justify-center text-gray-400">
                  <p>暂无聚类数据，请先点击"运行聚类分析"</p>
                </div>
              )}
            </Card>

            {/* 簇大小柱状图 */}
            <Card title="簇样本数量排行" className="shadow-sm lg:col-span-2">
              {getBarData().length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={getBarData()} margin={{ top: 20, right: 30, left: 20, bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={60} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" name="样本数量" fill="#45B7D1">
                      {getBarData().map((entry, index) => (
                        <BarCell
                          key={`cell-${index}`}
                          fill={CLUSTER_COLORS[index % CLUSTER_COLORS.length]}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-gray-400">
                  <p>暂无聚类数据，请先点击"运行聚类分析"</p>
                </div>
              )}
            </Card>
          </div>
        </TabPane>

        <TabPane tab="簇列表" key="clusters">
          <Card className="shadow-sm">
            <Table
              columns={clusterColumns}
              dataSource={clusters.map(c => ({...c, key: c.cluster_id}))}
              rowKey="cluster_id"
              loading={loading}
              pagination={{
                total: clusters.length,
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 个簇`,
              }}
            />

            {/* 展开的簇详情 */}
            {Array.from(expandedClusters).map(clusterId => {
              const cluster = clusters.find(c => c.cluster_id === clusterId)
              if (!cluster) return null

              return (
                <Card
                  key={`expand-${clusterId}`}
                  title={`簇 ${clusterId} 详情`}
                  className="mt-4 border-l-4 border-l-blue-500"
                >
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div>
                      <p className="text-gray-500 text-sm mb-1">样本数量</p>
                      <p className="text-lg font-bold">{cluster.sample_count}</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-sm mb-1">平均相似度</p>
                      <p className="text-lg font-bold">{(cluster.avg_similarity * 100).toFixed(2)}%</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-sm mb-1">主导类型</p>
                      <p className="text-lg font-bold">{cluster.dominant_type || '混合'}</p>
                    </div>
                  </div>

                  {cluster.top_keywords && (
                    <div className="mb-4">
                      <p className="text-gray-500 text-sm mb-2">关键词</p>
                      <Space wrap>
                        {cluster.top_keywords.map((kw, idx) => (
                          <Tag key={idx} color="blue">{kw.word} ({kw.count})</Tag>
                        ))}
                      </Space>
                    </div>
                  )}

                  {cluster.sample_examples && (
                    <div>
                      <p className="text-gray-500 text-sm mb-2">样本示例</p>
                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {cluster.sample_examples.map((sample, idx) => (
                          <div key={idx} className="p-3 bg-gray-50 rounded text-sm">
                            <p className="text-gray-700 line-clamp-2">{sample.content}</p>
                            {sample.metadata && (
                              <p className="text-xs text-gray-500 mt-1">
                                ID: {sample.id} | 类型: {sample.type}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )
            })}
          </Card>
        </TabPane>
      </Tabs>

      {/* 簇详情模态框 */}
      <Modal
        title={`簇 ${selectedCluster?.cluster_id} 详细信息`}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="back" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>,
          <Button key="download" type="primary" icon={<Download size={14} />}>
            导出数据
          </Button>
        ]}
        width={800}
      >
        {selectedCluster && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-gray-500 text-sm mb-1">簇ID</p>
                <p className="font-medium">{selectedCluster.cluster_id?.toString() || '-'}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm mb-1">样本数量</p>
                <p className="font-medium">
                  {typeof selectedCluster.sample_count === 'number' ? selectedCluster.sample_count : '-'}
                </p>
              </div>
              <div>
                <p className="text-gray-500 text-sm mb-1">平均相似度</p>
                {typeof selectedCluster.avg_similarity === 'number' ? (
                  <Progress
                    percent={Math.round(selectedCluster.avg_similarity * 100)}
                    size="small"
                  />
                ) : (
                  <p className="font-medium">-</p>
                )}
              </div>
              <div>
                <p className="text-gray-500 text-sm mb-1">聚类质量</p>
                <p className="font-medium">
                  {typeof selectedCluster.silhouette_score === 'number'
                    ? (selectedCluster.silhouette_score * 100).toFixed(2) + '%'
                    : 'N/A'}
                </p>
              </div>
            </div>

            {selectedCluster.factors && selectedCluster.factors.length > 0 && (
              <div>
                <p className="text-gray-500 text-sm mb-3">提取的因子</p>
                <div className="space-y-3">
                  {selectedCluster.factors.map((factor, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 rounded">
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-medium">{factor.name}</p>
                        <Tag color={
                          factor.factor_type === 'content_structure' ? 'blue' :
                          factor.factor_type === 'product_expression' ? 'orange' : 'purple'
                        }>
                          {factor.factor_type === 'content_structure' ? '内容结构' :
                           factor.factor_type === 'product_expression' ? '产品表达' : '用户运营'}
                        </Tag>
                      </div>
                      <p className="text-sm text-gray-600">{factor.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selectedCluster.sample_examples && (
              <div>
                <p className="text-gray-500 text-sm mb-3">样本列表</p>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {selectedCluster.sample_examples.map((sample, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 rounded">
                      <p className="text-sm text-gray-700">{sample.content}</p>
                      <p className="text-xs text-gray-500 mt-1">ID: {sample.id}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </PageContainer>
  )
}
