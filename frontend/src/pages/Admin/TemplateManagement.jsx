import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Eye, ToggleLeft } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import { getTemplateList, updateTemplateStatus, deleteTemplate } from '../../services/admin'
import { useAppStore } from '../../store/appStore'

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'name', title: '模板名称' },
  {
    key: 'category',
    title: '分类',
    render: (category) => (
      <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
        {category}
      </span>
    )
  },
  { key: 'author', title: '作者' },
  {
    key: 'status',
    title: '状态',
    render: (status) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
      }`}>
        {status === 'active' ? '已上架' : '已下架'}
      </span>
    )
  },
  { key: 'usageCount', title: '使用次数' },
  { key: 'createdAt', title: '创建时间' },
]

// 模拟数据
const mockTemplates = [
  { id: 1, name: '产品宣传模板', category: '营销', author: 'admin', status: 'active', usageCount: 1234, createdAt: '2026-01-01' },
  { id: 2, name: '企业宣传片模板', category: '企业', author: 'admin', status: 'active', usageCount: 856, createdAt: '2026-01-02' },
  { id: 3, name: '短视频模板', category: '社交', author: 'editor', status: 'inactive', usageCount: 567, createdAt: '2026-01-03' },
  { id: 4, name: '教育课程模板', category: '教育', author: 'editor', status: 'active', usageCount: 923, createdAt: '2026-01-04' },
  { id: 5, name: '婚礼视频模板', category: '生活', author: 'admin', status: 'active', usageCount: 456, createdAt: '2026-01-05' },
]

export default function TemplateManagement() {
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const templateList = useAppStore((state) => state.templateList)
  const setTemplateList = useAppStore((state) => state.setTemplateList)

  useEffect(() => {
    fetchTemplates()
  }, [filter])

  const fetchTemplates = async () => {
    try {
      setLoading(true)
      // 实际调用API
      // const data = await getTemplateList({ status: filter })
      // 模拟数据
      let filtered = mockTemplates
      if (filter !== 'all') {
        filtered = mockTemplates.filter(item => item.status === filter)
      }
      setTemplateList(filtered)
    } catch (error) {
      console.error('获取模板列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleStatus = async (template) => {
    const newStatus = template.status === 'active' ? 'inactive' : 'active'
    try {
      await updateTemplateStatus(template.id, newStatus)
      fetchTemplates()
    } catch (error) {
      console.error('更新模板状态失败:', error)
      alert('操作失败，请重试')
    }
  }

  const handleDelete = async (id) => {
    if (window.confirm('确定要删除这个模板吗？')) {
      try {
        await deleteTemplate(id)
        fetchTemplates()
      } catch (error) {
        console.error('删除模板失败:', error)
        alert('删除失败，请重试')
      }
    }
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-2">
      <button
        className="p-1 text-blue-600 hover:text-blue-800"
        title="预览"
      >
        <Eye size={16} />
      </button>
      <button
        className="p-1 text-purple-600 hover:text-purple-800"
        title="编辑"
      >
        <Edit size={16} />
      </button>
      <button
        onClick={() => toggleStatus(row)}
        className={`p-1 ${
          row.status === 'active' ? 'text-yellow-600 hover:text-yellow-800' : 'text-green-600 hover:text-green-800'
        }`}
        title={row.status === 'active' ? '下架' : '上架'}
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

  const filters = [
    { value: 'all', label: '全部' },
    { value: 'active', label: '已上架' },
    { value: 'inactive', label: '已下架' },
  ]

  return (
    <PageContainer
      title="模板管理"
      actions={
        <button
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={20} />
          <span>创建模板</span>
        </button>
      }
    >
      <div className="mb-6 flex space-x-2">
        {filters.map((item) => (
          <button
            key={item.value}
            onClick={() => setFilter(item.value)}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === item.value
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <Table
        columns={columns}
        data={templateList}
        actions={actions}
        loading={loading}
      />
    </PageContainer>
  )
}

