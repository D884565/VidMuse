import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, ChevronRight, ChevronDown } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import { getCategoryTree, createCategory, updateCategory, deleteCategory } from '../../services/admin'

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'name', title: '分类名称' },
  {
    key: 'level',
    title: '层级',
    render: (level) => (
      <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
        {level}级分类
      </span>
    )
  },
  { key: 'sort', title: '排序' },
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
  { key: 'createdAt', title: '创建时间' },
]

export default function CategoryManagement() {
  const [loading, setLoading] = useState(true)
  const [categories, setCategories] = useState([])
  const [expandedKeys, setExpandedKeys] = useState(new Set())
  const [modalVisible, setModalVisible] = useState(false)
  const [editingCategory, setEditingCategory] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    parentId: 0,
    level: 1,
    sort: 0,
    status: 1,
  })

  useEffect(() => {
    fetchCategories()
  }, [])

  const fetchCategories = async () => {
    try {
      setLoading(true)
      const data = await getCategoryTree()
      setCategories(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('获取分类树失败:', error)
      setCategories([])
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = (categoryId) => {
    const newExpanded = new Set(expandedKeys)
    if (newExpanded.has(categoryId)) {
      newExpanded.delete(categoryId)
    } else {
      newExpanded.add(categoryId)
    }
    setExpandedKeys(newExpanded)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingCategory) {
        await updateCategory(editingCategory.id, formData)
      } else {
        await createCategory(formData)
      }
      fetchCategories()
      setModalVisible(false)
      setFormData({ name: '', parentId: 0, level: 1, sort: 0, status: 1 })
      setEditingCategory(null)
    } catch (error) {
      console.error('保存分类失败:', error)
      alert('保存失败，请重试')
    }
  }

  const handleEdit = (category) => {
    setEditingCategory(category)
    setFormData({
      name: category.name,
      parentId: category.parentId || 0,
      level: category.level,
      sort: category.sort || 0,
      status: category.status || 1,
    })
    setModalVisible(true)
  }

  const handleDelete = async (categoryId) => {
    if (window.confirm('确定要删除这个分类吗？删除后子分类也会被删除！')) {
      try {
        await deleteCategory(categoryId)
        fetchCategories()
      } catch (error) {
        console.error('删除分类失败:', error)
        alert('删除失败，请重试')
      }
    }
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-2">
      <button
        onClick={() => handleEdit(row)}
        className="p-1 text-blue-600 hover:text-blue-800"
        title="编辑"
      >
        <Edit size={16} />
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

  // 递归渲染树形结构
  const renderTree = (items, level = 0) => {
    return items.map((item) => (
      <div key={item.id}>
        <tr className="hover:bg-gray-50">
          <td className="px-6 py-4 whitespace-nowrap">
            <div style={{ paddingLeft: `${level * 20}px` }} className="flex items-center">
              {item.children && item.children.length > 0 && (
                <button
                  onClick={() => toggleExpand(item.id)}
                  className="mr-2 text-gray-500 hover:text-gray-700"
                >
                  {expandedKeys.has(item.id) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
              )}
              {item.id}
            </div>
          </td>
          <td className="px-6 py-4 whitespace-nowrap">
            <div style={{ paddingLeft: `${level * 20}px` }}>{item.name}</div>
          </td>
          <td className="px-6 py-4 whitespace-nowrap">
            <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              {item.level}级分类
            </span>
          </td>
          <td className="px-6 py-4 whitespace-nowrap">{item.sort}</td>
          <td className="px-6 py-4 whitespace-nowrap">
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
              item.status === 1 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
            }`}>
              {item.status === 1 ? '启用' : '禁用'}
            </span>
          </td>
          <td className="px-6 py-4 whitespace-nowrap">{item.createdAt}</td>
          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
            {actions(item)}
          </td>
        </tr>
        {item.children && item.children.length > 0 && expandedKeys.has(item.id) && renderTree(item.children, level + 1)}
      </div>
    ))
  }

  return (
    <PageContainer
      title="分类管理"
      actions={
        <button
          onClick={() => setModalVisible(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={20} />
          <span>新增分类</span>
        </button>
      }
    >
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-500">加载中...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">分类名称</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">层级</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">排序</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {renderTree(categories)}
              </tbody>
            </table>
          </div>
        )}
        {!loading && categories.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            暂无分类数据
          </div>
        )}
      </div>

      {/* 新增/编辑弹窗 */}
      {modalVisible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">{editingCategory ? '编辑分类' : '新增分类'}</h3>
              <button onClick={() => setModalVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">分类名称</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">父分类ID</label>
                <input
                  type="number"
                  value={formData.parentId}
                  onChange={(e) => setFormData({ ...formData, parentId: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">0表示一级分类</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">层级</label>
                <input
                  type="number"
                  min="1"
                  max="3"
                  required
                  value={formData.level}
                  onChange={(e) => setFormData({ ...formData, level: parseInt(e.target.value) || 1 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">排序</label>
                <input
                  type="number"
                  value={formData.sort}
                  onChange={(e) => setFormData({ ...formData, sort: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">数字越小越靠前</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">状态</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={1}>启用</option>
                  <option value={0}>禁用</option>
                </select>
              </div>
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
