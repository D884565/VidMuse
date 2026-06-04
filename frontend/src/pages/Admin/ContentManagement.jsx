import { useState, useEffect } from 'react'
import { Eye, Trash2, Check, X } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import { getContentList, updateContentStatus, deleteContent } from '../../services/admin'
import { useAppStore } from '../../store/appStore'

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'title', title: '标题' },
  {
    key: 'type',
    title: '类型',
    render: (type) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        type === 'video' ? 'bg-blue-100 text-blue-800' :
        type === 'audio' ? 'bg-purple-100 text-purple-800' :
        'bg-green-100 text-green-800'
      }`}>
        {type === 'video' ? '视频' : type === 'audio' ? '音频' : '图片'}
      </span>
    )
  },
  { key: 'username', title: '上传用户' },
  {
    key: 'status',
    title: '状态',
    render: (status) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        status === 'approved' ? 'bg-green-100 text-green-800' :
        status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
        'bg-red-100 text-red-800'
      }`}>
        {status === 'approved' ? '已通过' : status === 'pending' ? '待审核' : '已拒绝'}
      </span>
    )
  },
  { key: 'createdAt', title: '上传时间' },
]

// 模拟数据
const mockContent = [
  { id: 1, title: '产品宣传视频', type: 'video', username: 'user1', status: 'approved', createdAt: '2026-06-01' },
  { id: 2, title: '背景音乐', type: 'audio', username: 'user2', status: 'pending', createdAt: '2026-06-02' },
  { id: 3, title: '产品封面图', type: 'image', username: 'user3', status: 'approved', createdAt: '2026-06-03' },
  { id: 4, title: '用户教程视频', type: 'video', username: 'user4', status: 'rejected', createdAt: '2026-06-04' },
  { id: 5, title: '音效素材', type: 'audio', username: 'user5', status: 'pending', createdAt: '2026-06-05' },
]

export default function ContentManagement() {
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const contentList = useAppStore((state) => state.contentList)
  const setContentList = useAppStore((state) => state.setContentList)

  useEffect(() => {
    fetchContent()
  }, [filter])

  const fetchContent = async () => {
    try {
      setLoading(true)
      // 实际调用API，传入filter参数
      // const data = await getContentList({ status: filter })
      // 模拟数据
      let filtered = mockContent
      if (filter !== 'all') {
        filtered = mockContent.filter(item => item.status === filter)
      }
      setContentList(filtered)
    } catch (error) {
      console.error('获取内容列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (id) => {
    try {
      await updateContentStatus(id, 'approved')
      fetchContent()
    } catch (error) {
      console.error('审核失败:', error)
      alert('操作失败，请重试')
    }
  }

  const handleReject = async (id) => {
    try {
      await updateContentStatus(id, 'rejected')
      fetchContent()
    } catch (error) {
      console.error('拒绝失败:', error)
      alert('操作失败，请重试')
    }
  }

  const handleDelete = async (id) => {
    if (window.confirm('确定要删除这个内容吗？')) {
      try {
        await deleteContent(id)
        fetchContent()
      } catch (error) {
        console.error('删除内容失败:', error)
        alert('删除失败，请重试')
      }
    }
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-2">
      <button
        className="p-1 text-blue-600 hover:text-blue-800"
        title="查看详情"
      >
        <Eye size={16} />
      </button>
      {row.status === 'pending' && (
        <>
          <button
            onClick={() => handleApprove(row.id)}
            className="p-1 text-green-600 hover:text-green-800"
            title="审核通过"
          >
            <Check size={16} />
          </button>
          <button
            onClick={() => handleReject(row.id)}
            className="p-1 text-yellow-600 hover:text-yellow-800"
            title="拒绝"
          >
            <X size={16} />
          </button>
        </>
      )}
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
    { value: 'pending', label: '待审核' },
    { value: 'approved', label: '已通过' },
    { value: 'rejected', label: '已拒绝' },
  ]

  return (
    <PageContainer title="内容管理">
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
        data={contentList}
        actions={actions}
        loading={loading}
      />
    </PageContainer>
  )
}

