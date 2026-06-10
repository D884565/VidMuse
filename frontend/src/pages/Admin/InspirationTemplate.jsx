import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Eye, ToggleLeft, BarChart3, X } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import LineChart from '../../components/Admin/Charts/LineChart'
import GaugeChart from '../../components/Admin/Charts/GaugeChart'
import {
  getFactorList, createFactor, updateFactor, deleteFactor, getFactorDetail,
  getStrategyList, createStrategy, updateStrategy, deleteStrategy, getStrategyDetail,
  getInspirationTemplateList, createInspirationTemplate, updateInspirationTemplate, deleteInspirationTemplate, getInspirationTemplateDetail,
} from '../../services/admin'

const TAB_NAMES = {
  FACTORS: 'factors',
  STRATEGIES: 'strategies',
  TEMPLATES: 'templates',
  ANALYTICS: 'analytics',
}

const factorColumns = [
  { key: 'id', title: 'ID' },
  { key: 'name', title: '因子名称' },
  {
    key: 'factor_type',
    title: '因子类型',
    render: (type) => {
      const typeMap = {
        'content_structure': '内容结构',
        'product_expression': '产品表达',
        'user_operation': '用户行为',
      }
      return <span>{typeMap[type] || type}</span>
    }
  },
  { key: 'popularity', title: '流行度', render: (val) => (val * 100).toFixed(0) + '%' },
  {
    key: 'status',
    title: '状态',
    render: (status) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        status === 1 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
      }`}>
        {status === 1 ? '启用' : '禁用'}
      </span>
    )
  },
  { key: 'success_rate', title: '成功率', render: (val) => val ? (val * 100).toFixed(1) + '%' : '0%' },
  { key: 'usage_count', title: '使用次数' },
  { key: 'created_at', title: '创建时间' },
]

const strategyColumns = [
  { key: 'id', title: 'ID' },
  { key: 'name', title: '策略名称' },
  { key: 'applicable_scenario', title: '适用场景' },
  { key: 'success_rate', title: '成功率' },
  { key: 'usage_count', title: '使用次数' },
  {
    key: 'status',
    title: '状态',
    render: (status) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        status === 1 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
      }`}>
        {status === 1 ? '启用' : '禁用'}
      </span>
    )
  },
  { key: 'created_at', title: '创建时间' },
]

const templateColumns = [
  { key: 'id', title: 'ID' },
  { key: 'name', title: '模板名称' },
  { key: 'category', title: '分类' },
  { key: 'version', title: '版本' },
  { key: 'success_rate', title: '成功率' },
  { key: 'usage_count', title: '使用次数' },
  {
    key: 'status',
    title: '状态',
    render: (status) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        status === 1 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
      }`}>
        {status === 1 ? '启用' : '禁用'}
      </span>
    )
  },
  { key: 'created_at', title: '创建时间' },
]

export default function InspirationTemplate() {
  const [activeTab, setActiveTab] = useState(TAB_NAMES.FACTORS)
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState([])
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: 20 })
  const [modalVisible, setModalVisible] = useState(false)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [detailItem, setDetailItem] = useState(null)
  const [formData, setFormData] = useState({})
  const [analyticsData, setAnalyticsData] = useState({
    factorStats: { total: 0, active: 0, successRate: 0 },
    strategyStats: { total: 0, active: 0, successRate: 0 },
    templateStats: { total: 0, active: 0, successRate: 0 },
    trendData: [],
    factorTypeDistribution: [],
    scenarioDistribution: [],
  })
  const [allFactors, setAllFactors] = useState([])
  const [allStrategies, setAllStrategies] = useState([])

  useEffect(() => {
    fetchData()
    // 预加载所有策略和因子，用于模板编辑时的选择
    if (activeTab === TAB_NAMES.TEMPLATES || activeTab === TAB_NAMES.ANALYTICS) {
      loadAllStrategiesAndFactors()
    }
  }, [activeTab, pagination.page])

  // 预加载所有策略和因子
  const loadAllStrategiesAndFactors = async () => {
    try {
      const [strategyRes, factorRes] = await Promise.all([
        getStrategyList({ page: 1, page_size: 1000 }),
        getFactorList({ page: 1, page_size: 1000 }),
      ])
      setAllStrategies(strategyRes?.list || [])
      setAllFactors(factorRes?.list || [])
    } catch (error) {
      console.error('加载策略和因子列表失败:', error)
    }
  }

  // 添加因子关联
  const addFactorRelation = (usageType) => {
    setFormData(prev => {
      const relations = prev.factor_relations || []
      return {
        ...prev,
        factor_relations: [
          ...relations,
          {
            factor_id: '',
            factor_usage_type: usageType,
            weight: usageType === 1 ? 0.5 : 0.3,
            sort_order: relations.length
          }
        ]
      }
    })
  }

  // 更新因子关联
  const updateFactorRelation = (index, usageType, field, value) => {
    setFormData(prev => {
      const relations = [...(prev.factor_relations || [])]
      // 找到对应类型的所有关系，并记录它们在原数组中的索引
      const typeIndices = relations
        .map((rel, idx) => ({ rel, idx }))
        .filter(item => item.rel.factor_usage_type === usageType)

      if (typeIndices[index]) {
        relations[typeIndices[index].idx][field] = value
      }
      return {
        ...prev,
        factor_relations: relations
      }
    })
  }

  // 删除因子关联
  const removeFactorRelation = (index, usageType) => {
    setFormData(prev => {
      const relations = [...(prev.factor_relations || [])]
      // 找到对应类型的所有关系，并记录它们在原数组中的索引
      const typeIndices = relations
        .map((rel, idx) => ({ rel, idx }))
        .filter(item => item.rel.factor_usage_type === usageType)

      if (typeIndices[index]) {
        relations.splice(typeIndices[index].idx, 1)
      }
      return {
        ...prev,
        factor_relations: relations
      }
    })
  }

  const fetchData = async () => {
    try {
      setLoading(true)
      let result
      const params = { page: pagination.page, page_size: pagination.page_size }

      switch (activeTab) {
        case TAB_NAMES.FACTORS:
          result = await getFactorList(params)
          break
        case TAB_NAMES.STRATEGIES:
          result = await getStrategyList(params)
          break
        case TAB_NAMES.TEMPLATES:
          result = await getInspirationTemplateList(params)
          break
        case TAB_NAMES.ANALYTICS:
          await fetchAnalyticsData()
          return
        default:
          result = []
      }

      // 后端返回格式：{ list: [...], pagination: { total, page, page_size } }
      setData(result?.list || [])
      setPagination(prev => ({
        ...prev,
        total: result?.pagination?.total || 0,
      }))
    } catch (error) {
      console.error(`获取${activeTab}列表失败:`, error)
      setData([])
    } finally {
      setLoading(false)
    }
  }

  // 获取分析数据
  const fetchAnalyticsData = async () => {
    try {
      // 获取所有数据用于统计
      const [factorRes, strategyRes, templateRes] = await Promise.all([
        getFactorList({ page: 1, page_size: 1000 }),
        getStrategyList({ page: 1, page_size: 1000 }),
        getInspirationTemplateList({ page: 1, page_size: 1000 }),
      ])

      const factors = factorRes?.list || []
      const strategies = strategyRes?.list || []
      const templates = templateRes?.list || []

      // 统计基本信息
      const factorStats = {
        total: factors.length,
        active: factors.filter(f => f.status === 1).length,
        successRate: factors.length ? Math.round(factors.reduce((sum, f) => sum + (f.success_rate || 0), 0) / factors.length * 100) : 0,
      }

      const strategyStats = {
        total: strategies.length,
        active: strategies.filter(s => s.status === 1).length,
        successRate: strategies.length ? Math.round(strategies.reduce((sum, s) => sum + (s.success_rate || 0), 0) / strategies.length * 100) : 0,
      }

      const templateStats = {
        total: templates.length,
        active: templates.filter(t => t.status === 1).length,
        successRate: templates.length ? Math.round(templates.reduce((sum, t) => sum + (t.success_rate || 0), 0) / templates.length * 100) : 0,
      }

      // 生成趋势数据（模拟近7天数据）
      const trendData = Array.from({ length: 7 }, (_, i) => {
        const date = new Date()
        date.setDate(date.getDate() - 6 + i)
        return {
          date: date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }),
          factors: Math.floor(Math.random() * 10),
          strategies: Math.floor(Math.random() * 5),
          templates: Math.floor(Math.random() * 3),
        }
      })

      // 因子类型分布
      const factorTypeMap = {}
      factors.forEach(f => {
        factorTypeMap[f.factor_type] = (factorTypeMap[f.factor_type] || 0) + 1
      })
      const factorTypeDistribution = Object.entries(factorTypeMap).map(([type, count]) => ({
        name: {
          'content_structure': '内容结构',
          'product_expression': '产品表达',
          'user_operation': '用户行为',
        }[type] || type,
        value: count,
      }))

      // 策略适用场景分布
      const scenarioMap = {}
      strategies.forEach(s => {
        const scenarios = s.applicable_scenarios || []
        scenarios.forEach(scenario => {
          scenarioMap[scenario] = (scenarioMap[scenario] || 0) + 1
        })
      })
      const scenarioDistribution = Object.entries(scenarioMap).map(([scenario, count]) => ({
        name: scenario,
        value: count,
      }))

      setAnalyticsData({
        factorStats,
        strategyStats,
        templateStats,
        trendData,
        factorTypeDistribution,
        scenarioDistribution,
      })
    } catch (error) {
      console.error('获取分析数据失败:', error)
    }
  }

  // 查看详情
  const handleViewDetail = async (item) => {
    try {
      setLoading(true)
      let detail
      switch (activeTab) {
        case TAB_NAMES.FACTORS:
          detail = await getFactorDetail(item.id)
          break
        case TAB_NAMES.STRATEGIES:
          detail = await getStrategyDetail(item.id)
          break
        case TAB_NAMES.TEMPLATES:
          detail = await getInspirationTemplateDetail(item.id)
          break
      }
      setDetailItem(detail)
      setDetailModalVisible(true)
    } catch (error) {
      console.error('获取详情失败:', error)
      alert('获取详情失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingItem) {
        switch (activeTab) {
          case TAB_NAMES.FACTORS:
            await updateFactor(editingItem.id, formData)
            break
          case TAB_NAMES.STRATEGIES:
            await updateStrategy(editingItem.id, formData)
            break
          case TAB_NAMES.TEMPLATES:
            await updateInspirationTemplate(editingItem.id, formData)
            break
        }
      } else {
        switch (activeTab) {
          case TAB_NAMES.FACTORS:
            await createFactor(formData)
            break
          case TAB_NAMES.STRATEGIES:
            await createStrategy(formData)
            break
          case TAB_NAMES.TEMPLATES:
            await createInspirationTemplate(formData)
            break
        }
      }
      fetchData()
      setModalVisible(false)
      setFormData({})
      setEditingItem(null)
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败，请重试')
    }
  }

  const handleEdit = async (item) => {
    setEditingItem(item)
    // 如果是模板，需要获取完整详情（包含关联的因子）
    if (activeTab === TAB_NAMES.TEMPLATES) {
      try {
        const detail = await getInspirationTemplateDetail(item.id)
        // 转换因子格式为表单需要的格式
        const factorRelations = [
          ...(detail.required_factors || []).map(f => ({
            factor_id: f.factor_id,
            factor_usage_type: 1,
            weight: f.weight || 0.5,
            sort_order: f.sort_order || 0
          })),
          ...(detail.optional_factors || []).map(f => ({
            factor_id: f.factor_id,
            factor_usage_type: 2,
            weight: f.weight || 0.3,
            sort_order: f.sort_order || 0
          }))
        ]
        setFormData({ ...detail, factor_relations: factorRelations })
      } catch (error) {
        console.error('获取模板详情失败:', error)
        setFormData({ ...item })
      }
    } else {
      setFormData({ ...item })
    }
    setModalVisible(true)
  }

  const handleDelete = async (id) => {
    if (window.confirm('确定要删除吗？删除后无法恢复！')) {
      try {
        switch (activeTab) {
          case TAB_NAMES.FACTORS:
            await deleteFactor(id)
            break
          case TAB_NAMES.STRATEGIES:
            await deleteStrategy(id)
            break
          case TAB_NAMES.TEMPLATES:
            await deleteInspirationTemplate(id)
            break
        }
        fetchData()
      } catch (error) {
        console.error('删除失败:', error)
        alert('删除失败，请重试')
      }
    }
  }

  const toggleStatus = async (item) => {
    const newStatus = item.status === 1 ? 0 : 1
    try {
      switch (activeTab) {
        case TAB_NAMES.FACTORS:
          await updateFactor(item.id, { status: newStatus })
          break
        case TAB_NAMES.STRATEGIES:
          await updateStrategy(item.id, { status: newStatus })
          break
        case TAB_NAMES.TEMPLATES:
          await updateInspirationTemplate(item.id, { status: newStatus })
          break
      }
      fetchData()
    } catch (error) {
      console.error('更新状态失败:', error)
      alert('操作失败，请重试')
    }
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={() => handleViewDetail(row)}
        className="p-1 text-blue-600 hover:text-blue-800"
        title="查看详情"
      >
        <Eye size={16} />
      </button>
      <button
        onClick={() => handleEdit(row)}
        className="p-1 text-purple-600 hover:text-purple-800"
        title="编辑"
      >
        <Edit size={16} />
      </button>
      <button
        onClick={() => toggleStatus(row)}
        className={`p-1 ${
          row.status === 1 ? 'text-yellow-600 hover:text-yellow-800' : 'text-green-600 hover:text-green-800'
        }`}
        title={row.status === 1 ? '禁用' : '启用'}
      >
        <ToggleLeft size={16} />
      </button>
      <button
        onClick={() => handleDelete(row.id)}
        className="p-1 text-red-600 hover:text-red-800"
        title="删除"
      >
        <Trash2 size={16} />
      </button>
    </div>
  )

  const getColumns = () => {
    switch (activeTab) {
      case TAB_NAMES.FACTORS:
        return factorColumns
      case TAB_NAMES.STRATEGIES:
        return strategyColumns
      case TAB_NAMES.TEMPLATES:
        return templateColumns
      default:
        return []
    }
  }

  const renderForm = () => {
    // 根据不同的标签页渲染不同的表单字段
    switch (activeTab) {
      case TAB_NAMES.FACTORS:
        return (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">因子名称</label>
              <input
                type="text"
                required
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">因子类型</label>
              <select
                value={formData.factor_type || ''}
                onChange={(e) => setFormData({ ...formData, factor_type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">请选择</option>
                <option value="content_structure">内容结构</option>
                <option value="product_expression">产品表达</option>
                <option value="user_operation">用户行为</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">流行度</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={formData.popularity || 0}
                onChange={(e) => setFormData({ ...formData, popularity: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">状态</label>
              <select
                value={formData.status ?? 1}
                onChange={(e) => setFormData({ ...formData, status: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={1}>启用</option>
                <option value={0}>禁用</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows="3"
              />
            </div>
          </>
        )
      case TAB_NAMES.STRATEGIES:
        return (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">策略名称</label>
              <input
                type="text"
                required
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">适用场景</label>
              <input
                type="text"
                value={formData.applicable_scenario || ''}
                onChange={(e) => setFormData({ ...formData, applicable_scenario: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例如：短视频、产品宣传等"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">成功阈值</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={formData.success_threshold || 0.7}
                onChange={(e) => setFormData({ ...formData, success_threshold: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">状态</label>
              <select
                value={formData.status ?? 1}
                onChange={(e) => setFormData({ ...formData, status: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={1}>启用</option>
                <option value={0}>禁用</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">策略描述</label>
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows="3"
              />
            </div>
          </>
        )
      case TAB_NAMES.TEMPLATES:
        return (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">模板名称</label>
              <input
                type="text"
                required
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">关联策略</label>
              <select
                value={formData.strategy_id || ''}
                onChange={(e) => setFormData({ ...formData, strategy_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">请选择策略</option>
                {allStrategies.map(strategy => (
                  <option key={strategy.strategy_id} value={strategy.strategy_id}>
                    {strategy.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
              <input
                type="text"
                value={formData.category || ''}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">版本号</label>
              <input
                type="text"
                value={formData.version || '1.0.0'}
                onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例如：1.0.0"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">状态</label>
              <select
                value={formData.status ?? 1}
                onChange={(e) => setFormData({ ...formData, status: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={1}>启用</option>
                <option value={0}>禁用</option>
              </select>
            </div>

            {/* 关联因子 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">关联因子</label>

              {/* 必填因子 */}
              <div className="mb-4">
                <h4 className="text-sm font-medium text-red-600 mb-2 flex items-center justify-between">
                  <span>必填因子</span>
                  <button
                    type="button"
                    onClick={() => addFactorRelation(1)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    + 添加
                  </button>
                </h4>
                {formData.factor_relations?.filter(r => r.factor_usage_type === 1).map((relation, index) => (
                  <div key={index} className="flex items-center space-x-2 mb-2">
                    <select
                      value={relation.factor_id}
                      onChange={(e) => updateFactorRelation(index, 1, 'factor_id', e.target.value)}
                      className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded"
                      required
                    >
                      <option value="">请选择因子</option>
                      {allFactors.map(factor => (
                        <option key={factor.factor_id} value={factor.factor_id}>
                          {factor.name}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={relation.weight || 0.5}
                      onChange={(e) => updateFactorRelation(index, 1, 'weight', parseFloat(e.target.value))}
                      className="w-20 px-2 py-1 text-sm border border-gray-300 rounded"
                      placeholder="权重"
                    />
                    <button
                      type="button"
                      onClick={() => removeFactorRelation(index, 1)}
                      className="p-1 text-red-600 hover:text-red-800"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>

              {/* 可选因子 */}
              <div>
                <h4 className="text-sm font-medium text-yellow-600 mb-2 flex items-center justify-between">
                  <span>可选因子</span>
                  <button
                    type="button"
                    onClick={() => addFactorRelation(2)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    + 添加
                  </button>
                </h4>
                {formData.factor_relations?.filter(r => r.factor_usage_type === 2).map((relation, index) => (
                  <div key={index} className="flex items-center space-x-2 mb-2">
                    <select
                      value={relation.factor_id}
                      onChange={(e) => updateFactorRelation(index, 2, 'factor_id', e.target.value)}
                      className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded"
                    >
                      <option value="">请选择因子</option>
                      {allFactors.map(factor => (
                        <option key={factor.factor_id} value={factor.factor_id}>
                          {factor.name}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={relation.weight || 0.3}
                      onChange={(e) => updateFactorRelation(index, 2, 'weight', parseFloat(e.target.value))}
                      className="w-20 px-2 py-1 text-sm border border-gray-300 rounded"
                      placeholder="权重"
                    />
                    <button
                      type="button"
                      onClick={() => removeFactorRelation(index, 2)}
                      className="p-1 text-red-600 hover:text-red-800"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">模板内容</label>
              <textarea
                value={formData.content || ''}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows="4"
                placeholder="模板prompt内容"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows="3"
                placeholder="模板描述"
              />
            </div>
          </>
        )
      default:
        return null
    }
  }

  return (
    <PageContainer
      title="灵感模板管理"
      actions={
        <button
          onClick={() => setModalVisible(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={20} />
          <span>新增{activeTab === TAB_NAMES.FACTORS ? '因子' : activeTab === TAB_NAMES.STRATEGIES ? '策略' : '模板'}</span>
        </button>
      }
    >
      {/* 标签页切换 */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab(TAB_NAMES.FACTORS)}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === TAB_NAMES.FACTORS
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            创作因子
          </button>
          <button
            onClick={() => setActiveTab(TAB_NAMES.STRATEGIES)}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === TAB_NAMES.STRATEGIES
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            创作策略
          </button>
          <button
            onClick={() => setActiveTab(TAB_NAMES.TEMPLATES)}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === TAB_NAMES.TEMPLATES
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            灵感模板
          </button>
          <button
            onClick={() => setActiveTab(TAB_NAMES.ANALYTICS)}
            className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-1 ${
              activeTab === TAB_NAMES.ANALYTICS
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <BarChart3 size={16} />
            <span>数据统计</span>
          </button>
        </nav>
      </div>

      {/* 列表 */}
      {activeTab !== TAB_NAMES.ANALYTICS ? (
        <>
          <Table
            columns={getColumns()}
            data={data}
            actions={actions}
            loading={loading}
          />

          {/* 分页信息 */}
          <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
            <div>
              共 {pagination.total} 条记录，第 {pagination.page} 页 / 共 {Math.ceil(pagination.total / pagination.page_size)} 页
            </div>
            <div className="space-x-2">
              <button
                onClick={() => setPagination(prev => ({ ...prev, page: Math.max(1, prev.page - 1) }))}
                disabled={pagination.page <= 1}
                className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
              >
                上一页
              </button>
              <button
                onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                disabled={pagination.page >= Math.ceil(pagination.total / pagination.page_size)}
                className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
              >
                下一页
              </button>
            </div>
          </div>
        </>
      ) : (
        /* 统计分析页面 */
        <div className="space-y-6">
          {/* 统计卡片 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">创作因子</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">总数</span>
                  <span className="font-semibold">{analyticsData.factorStats.total}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">启用</span>
                  <span className="font-semibold text-green-600">{analyticsData.factorStats.active}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">平均成功率</span>
                  <span className="font-semibold text-blue-600">{analyticsData.factorStats.successRate}%</span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">创作策略</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">总数</span>
                  <span className="font-semibold">{analyticsData.strategyStats.total}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">启用</span>
                  <span className="font-semibold text-green-600">{analyticsData.strategyStats.active}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">平均成功率</span>
                  <span className="font-semibold text-blue-600">{analyticsData.strategyStats.successRate}%</span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">灵感模板</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">总数</span>
                  <span className="font-semibold">{analyticsData.templateStats.total}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">启用</span>
                  <span className="font-semibold text-green-600">{analyticsData.templateStats.active}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">平均成功率</span>
                  <span className="font-semibold text-blue-600">{analyticsData.templateStats.successRate}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* 图表 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LineChart
              data={analyticsData.trendData}
              xKey="date"
              yKey="factors"
              title="近7天新增趋势"
              color="#3b82f6"
            />

            <div className="grid grid-cols-2 gap-6">
              <GaugeChart
                value={analyticsData.factorStats.successRate}
                title="因子成功率"
                color="#3b82f6"
              />
              <GaugeChart
                value={analyticsData.strategyStats.successRate}
                title="策略成功率"
                color="#10b981"
              />
              <GaugeChart
                value={analyticsData.templateStats.successRate}
                title="模板成功率"
                color="#f59e0b"
              />
            </div>
          </div>

          {/* 分布统计 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">因子类型分布</h3>
              <div className="space-y-3">
                {analyticsData.factorTypeDistribution.map((item, index) => (
                  <div key={index} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>{item.name}</span>
                      <span className="font-medium">{item.value} 个</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{
                          width: `${analyticsData.factorStats.total ? (item.value / analyticsData.factorStats.total) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">策略场景分布</h3>
              <div className="space-y-3">
                {analyticsData.scenarioDistribution.map((item, index) => (
                  <div key={index} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>{item.name}</span>
                      <span className="font-medium">{item.value} 个</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-green-600 h-2 rounded-full"
                        style={{
                          width: `${analyticsData.strategyStats.total ? (item.value / analyticsData.strategyStats.total) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 分页信息 */}
      <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
        <div>
          共 {pagination.total} 条记录，第 {pagination.page} 页 / 共 {Math.ceil(pagination.total / pagination.page_size)} 页
        </div>
        <div className="space-x-2">
          <button
            onClick={() => setPagination(prev => ({ ...prev, page: Math.max(1, prev.page - 1) }))}
            disabled={pagination.page <= 1}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <button
            onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
            disabled={pagination.page >= Math.ceil(pagination.total / pagination.page_size)}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            下一页
          </button>
        </div>
      </div>

      {/* 新增/编辑弹窗 */}
      {modalVisible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-2xl">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">
                {editingItem ? '编辑' : '新增'}
                {activeTab === TAB_NAMES.FACTORS ? '创作因子' : activeTab === TAB_NAMES.STRATEGIES ? '创作策略' : '灵感模板'}
              </h3>
              <button onClick={() => setModalVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              {renderForm()}
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setModalVisible(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  保存
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 详情弹窗 */}
      {detailModalVisible && detailItem && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">
                {activeTab === TAB_NAMES.FACTORS ? '因子详情' : activeTab === TAB_NAMES.STRATEGIES ? '策略详情' : '模板详情'}
              </h3>
              <button onClick={() => setDetailModalVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-6">
              {/* 因子详情 */}
              {activeTab === TAB_NAMES.FACTORS && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">因子名称</label>
                      <p className="text-gray-900">{detailItem.name}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">因子ID</label>
                      <p className="text-gray-900 font-mono text-sm">{detailItem.factor_id}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">因子类型</label>
                      <p className="text-gray-900">
                        {
                          {
                            'content_structure': '内容结构',
                            'product_expression': '产品表达',
                            'user_operation': '用户行为',
                          }[detailItem.factor_type] || detailItem.factor_type
                        }
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">权重</label>
                      <p className="text-gray-900">{detailItem.weight}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">状态</label>
                      <p className={`text-gray-900 ${detailItem.status === 1 ? 'text-green-600' : 'text-gray-500'}`}>
                        {detailItem.status === 1 ? '启用' : '禁用'}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">成功率</label>
                      <p className="text-gray-900">{(detailItem.success_rate * 100).toFixed(2)}%</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">使用次数</label>
                      <p className="text-gray-900">{detailItem.usage_count}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">创建时间</label>
                      <p className="text-gray-900">{detailItem.created_at}</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">描述</label>
                    <p className="text-gray-900 whitespace-pre-wrap">{detailItem.description || '无'}</p>
                  </div>

                  {detailItem.data_schema && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">数据结构</label>
                      <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto">
                        {JSON.stringify(detailItem.data_schema, null, 2)}
                      </pre>
                    </div>
                  )}

                  {detailItem.example && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">示例</label>
                      <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto">
                        {JSON.stringify(detailItem.example, null, 2)}
                      </pre>
                    </div>
                  )}

                  {detailItem.tags && detailItem.tags.length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">标签</label>
                      <div className="flex flex-wrap gap-2">
                        {detailItem.tags.map((tag, index) => (
                          <span key={index} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 策略详情 */}
              {activeTab === TAB_NAMES.STRATEGIES && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">策略名称</label>
                      <p className="text-gray-900">{detailItem.name}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">策略ID</label>
                      <p className="text-gray-900 font-mono text-sm">{detailItem.strategy_id}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">适用场景</label>
                      <p className="text-gray-900">{detailItem.applicable_scenario || '无'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">成功阈值</label>
                      <p className="text-gray-900">{detailItem.success_threshold}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">状态</label>
                      <p className={`text-gray-900 ${detailItem.status === 1 ? 'text-green-600' : 'text-gray-500'}`}>
                        {detailItem.status === 1 ? '启用' : '禁用'}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">成功率</label>
                      <p className="text-gray-900">{(detailItem.success_rate * 100).toFixed(2)}%</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">使用次数</label>
                      <p className="text-gray-900">{detailItem.usage_count}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">创建时间</label>
                      <p className="text-gray-900">{detailItem.created_at}</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">策略描述</label>
                    <p className="text-gray-900 whitespace-pre-wrap">{detailItem.description || '无'}</p>
                  </div>

                  {detailItem.core_logic && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">核心逻辑</label>
                      <p className="text-gray-900 whitespace-pre-wrap">{detailItem.core_logic}</p>
                    </div>
                  )}

                  {detailItem.combination_rules && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">组合规则</label>
                      <p className="text-gray-900 whitespace-pre-wrap">{detailItem.combination_rules}</p>
                    </div>
                  )}

                  {detailItem.required_factor_types && detailItem.required_factor_types.length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">必填因子类型</label>
                      <div className="flex flex-wrap gap-2">
                        {detailItem.required_factor_types.map((type, index) => (
                          <span key={index} className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded">
                            {type}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {detailItem.optional_factor_types && detailItem.optional_factor_types.length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">可选因子类型</label>
                      <div className="flex flex-wrap gap-2">
                        {detailItem.optional_factor_types.map((type, index) => (
                          <span key={index} className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded">
                            {type}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {detailItem.tags && detailItem.tags.length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">标签</label>
                      <div className="flex flex-wrap gap-2">
                        {detailItem.tags.map((tag, index) => (
                          <span key={index} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 模板详情 */}
              {activeTab === TAB_NAMES.TEMPLATES && (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">模板名称</label>
                      <p className="text-gray-900">{detailItem.name}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">模板ID</label>
                      <p className="text-gray-900 font-mono text-sm">{detailItem.template_id}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">分类</label>
                      <p className="text-gray-900">{detailItem.category || '无'}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">版本</label>
                      <p className="text-gray-900">{detailItem.version}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">状态</label>
                      <p className={`text-gray-900 ${detailItem.status === 1 ? 'text-green-600' : 'text-gray-500'}`}>
                        {detailItem.status === 1 ? '启用' : '禁用'}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">成功率</label>
                      <p className="text-gray-900">{(detailItem.success_rate * 100).toFixed(2)}%</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">使用次数</label>
                      <p className="text-gray-900">{detailItem.usage_count}</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">创建时间</label>
                      <p className="text-gray-900">{detailItem.created_at}</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">模板描述</label>
                    <p className="text-gray-900 whitespace-pre-wrap">{detailItem.description || '无'}</p>
                  </div>

                  {detailItem.content && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">模板内容</label>
                      <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto whitespace-pre-wrap">
                        {detailItem.content}
                      </pre>
                    </div>
                  )}

                  {/* 关联策略 */}
                  {detailItem.strategy && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">关联策略</label>
                      <div className="bg-blue-50 p-4 rounded-lg">
                        <p className="font-medium">{detailItem.strategy.name}</p>
                        <p className="text-sm text-gray-600 mt-1">{detailItem.strategy.description}</p>
                      </div>
                    </div>
                  )}

                  {/* 关联因子 */}
                  {(detailItem.required_factors?.length > 0 || detailItem.optional_factors?.length > 0) && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-3">关联因子</label>

                      {detailItem.required_factors?.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-red-600 mb-2">必填因子</h4>
                          <div className="space-y-2">
                            {detailItem.required_factors.map((factor, index) => (
                              <div key={index} className="bg-red-50 p-3 rounded-lg">
                                <div className="flex justify-between">
                                  <span className="font-medium">{factor.name}</span>
                                  <span className="text-xs text-gray-500">权重: {factor.weight}</span>
                                </div>
                                <p className="text-sm text-gray-600 mt-1">{factor.description}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {detailItem.optional_factors?.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-yellow-600 mb-2">可选因子</h4>
                          <div className="space-y-2">
                            {detailItem.optional_factors.map((factor, index) => (
                              <div key={index} className="bg-yellow-50 p-3 rounded-lg">
                                <div className="flex justify-between">
                                  <span className="font-medium">{factor.name}</span>
                                  <span className="text-xs text-gray-500">权重: {factor.weight}</span>
                                </div>
                                <p className="text-sm text-gray-600 mt-1">{factor.description}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {detailItem.combination_example && (
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">组合示例</label>
                      <pre className="bg-gray-50 p-4 rounded-lg text-sm overflow-x-auto">
                        {JSON.stringify(detailItem.combination_example, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end pt-4">
                <button
                  type="button"
                  onClick={() => setDetailModalVisible(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
