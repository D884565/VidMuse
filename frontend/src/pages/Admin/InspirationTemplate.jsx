import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Eye, ToggleLeft } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import {
  getFactorList, createFactor, updateFactor, deleteFactor,
  getStrategyList, createStrategy, updateStrategy, deleteStrategy,
  getInspirationTemplateList, createInspirationTemplate, updateInspirationTemplate, deleteInspirationTemplate,
} from '../../services/admin'

const TAB_NAMES = {
  FACTORS: 'factors',
  STRATEGIES: 'strategies',
  TEMPLATES: 'templates',
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
  { key: 'weight', title: '权重' },
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
  { key: 'success_rate', title: '成功率' },
  { key: 'created_at', title: '创建时间' },
]

const strategyColumns = [
  { key: 'id', title: 'ID' },
  { key: 'name', title: '策略名称' },
  { key: 'applicable_scenario', title: '适用场景' },
  { key: 'success_rate', title: '成功率' },
  { key: 'use_count', title: '使用次数' },
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
  { key: 'use_count', title: '使用次数' },
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
  const [editingItem, setEditingItem] = useState(null)
  const [formData, setFormData] = useState({})

  useEffect(() => {
    fetchData()
  }, [activeTab, pagination.page])

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
        default:
          result = []
      }

      setData(Array.isArray(result) ? result : result?.list || [])
      setPagination(prev => ({
        ...prev,
        total: result?.total || result?.length || 0,
      }))
    } catch (error) {
      console.error(`获取${activeTab}列表失败:`, error)
      setData([])
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

  const handleEdit = (item) => {
    setEditingItem(item)
    setFormData({ ...item })
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
              <label className="block text-sm font-medium text-gray-700 mb-1">权重</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={formData.weight || 0}
                onChange={(e) => setFormData({ ...formData, weight: parseFloat(e.target.value) })}
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
        </nav>
      </div>

      {/* 列表 */}
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
    </PageContainer>
  )
}
