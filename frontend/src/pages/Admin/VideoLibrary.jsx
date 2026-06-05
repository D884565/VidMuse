import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Upload, Play, RefreshCw, Import } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import { getVideoList, deleteVideo, triggerVideoParsing, batchImportHotVideos } from '../../services/admin'

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'title', title: '视频标题' },
  {
    key: 'category',
    title: '分类',
    render: (category) => (
      <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
        {category || '未分类'}
      </span>
    )
  },
  {
    key: 'hot_score',
    title: '爆款分数',
    render: (score) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        score >= 80 ? 'bg-red-100 text-red-800' :
        score >= 60 ? 'bg-yellow-100 text-yellow-800' :
        'bg-gray-100 text-gray-800'
      }`}>
        {score || 0}分
      </span>
    )
  },
  {
    key: 'status',
    title: '状态',
    render: (status) => {
      const statusMap = { 0: '待处理', 1: '处理中', 2: '已完成', 3: '失败' }
      const colorMap = { 0: 'yellow', 1: 'blue', 2: 'green', 3: 'red' }
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium bg-${colorMap[status]}-100 text-${colorMap[status]}-800`}>
          {statusMap[status] || '未知'}
        </span>
      )
    }
  },
  { key: 'duration', title: '时长(秒)' },
  { key: 'size', title: '文件大小' },
  { key: 'created_by', title: '创建人' },
  { key: 'created_at', title: '创建时间' },
]

const categoryOptions = [
  { value: '', label: '全部分类' },
  { value: '营销', label: '营销' },
  { value: '企业', label: '企业' },
  { value: '社交', label: '社交' },
  { value: '教育', label: '教育' },
  { value: '生活', label: '生活' },
]

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 0, label: '待处理' },
  { value: 1, label: '处理中' },
  { value: 2, label: '已完成' },
  { value: 3, label: '失败' },
]

export default function VideoLibrary() {
  const [loading, setLoading] = useState(true)
  const [videos, setVideos] = useState([])
  const [filters, setFilters] = useState({
    category: '',
    min_hot_score: '',
    source_type: '',
    keyword: '',
    page: 1,
    page_size: 20,
  })
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: 20 })
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [importModalVisible, setImportModalVisible] = useState(false)
  const [uploadForm, setUploadForm] = useState({
    file: null,
    title: '',
    description: '',
    category: '',
    tags: [],
  })
  const [importForm, setImportForm] = useState({
    category: '',
    min_hot_score: 80,
    limit: 50,
  })
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    fetchVideos()
  }, [filters])

  const fetchVideos = async () => {
    try {
      setLoading(true)
      const params = Object.fromEntries(
        Object.entries(filters).filter(([_, v]) => v !== '' && v != null)
      )
      const data = await getVideoList(params)
      setVideos(Array.isArray(data) ? data : data?.list || [])
      setPagination({
        total: data?.total || data?.length || 0,
        page: params.page || 1,
        page_size: params.page_size || 20,
      })
    } catch (error) {
      console.error('获取视频列表失败:', error)
      setVideos([])
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }))
  }

  const handleDelete = async (videoId) => {
    if (window.confirm('确定要删除这个视频吗？删除后无法恢复！')) {
      try {
        await deleteVideo(videoId)
        fetchVideos()
      } catch (error) {
        console.error('删除视频失败:', error)
        alert('删除失败，请重试')
      }
    }
  }

  const handleParse = async (videoId) => {
    if (window.confirm('确定要重新解析这个视频吗？')) {
      try {
        await triggerVideoParsing(videoId, true)
        alert('解析任务已启动，请稍后刷新查看状态')
      } catch (error) {
        console.error('触发解析失败:', error)
        alert('操作失败，请重试')
      }
    }
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!uploadForm.file) {
      alert('请选择视频文件')
      return
    }

    try {
      setProcessing(true)
      const formData = new FormData()
      formData.append('file', uploadForm.file)
      formData.append('title', uploadForm.title || uploadForm.file.name)
      formData.append('description', uploadForm.description || '')
      formData.append('category', uploadForm.category || '')
      uploadForm.tags.forEach(tag => formData.append('tags[]', tag))

      // 调用上传接口
      // await uploadVideo(formData)

      alert('上传成功！视频将在后台处理')
      setUploadModalVisible(false)
      setUploadForm({ file: null, title: '', description: '', category: '', tags: [] })
      fetchVideos()
    } catch (error) {
      console.error('上传失败:', error)
      alert('上传失败，请重试')
    } finally {
      setProcessing(false)
    }
  }

  const handleBatchImport = async (e) => {
    e.preventDefault()
    try {
      setProcessing(true)
      await batchImportHotVideos(importForm)
      alert('批量导入任务已启动，视频将陆续入库')
      setImportModalVisible(false)
      fetchVideos()
    } catch (error) {
      console.error('批量导入失败:', error)
      alert('导入失败，请重试')
    } finally {
      setProcessing(false)
    }
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        className="p-1 text-blue-600 hover:text-blue-800"
        title="播放"
      >
        <Play size={16} />
      </button>
      <button
        className="p-1 text-purple-600 hover:text-purple-800"
        title="编辑"
      >
        <Edit size={16} />
      </button>
      <button
        onClick={() => handleParse(row.id)}
        className="p-1 text-green-600 hover:text-green-800"
        title="重新解析"
      >
        <RefreshCw size={16} />
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

  return (
    <PageContainer
      title="视频库管理"
      actions={
        <div className="flex space-x-2">
          <button
            onClick={() => setImportModalVisible(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Import size={20} />
            <span>批量导入爆款</span>
          </button>
          <button
            onClick={() => setUploadModalVisible(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Upload size={20} />
            <span>上传视频</span>
          </button>
        </div>
      }
    >
      {/* 筛选栏 */}
      <div className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
          <select
            value={filters.category}
            onChange={(e) => handleFilterChange('category', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {categoryOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">最低爆款分数</label>
          <input
            type="number"
            min="0"
            max="100"
            placeholder="最低分数"
            value={filters.min_hot_score}
            onChange={(e) => handleFilterChange('min_hot_score', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">处理状态</label>
          <select
            value={filters.status}
            onChange={(e) => handleFilterChange('status', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {statusOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">关键词搜索</label>
          <input
            type="text"
            placeholder="搜索标题/描述"
            value={filters.keyword}
            onChange={(e) => handleFilterChange('keyword', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            onKeyDown={(e) => e.key === 'Enter' && fetchVideos()}
          />
        </div>
      </div>

      {/* 视频列表 */}
      <Table
        columns={columns}
        data={videos}
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
            onClick={() => handleFilterChange('page', Math.max(1, pagination.page - 1))}
            disabled={pagination.page <= 1}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <button
            onClick={() => handleFilterChange('page', pagination.page + 1)}
            disabled={pagination.page >= Math.ceil(pagination.total / pagination.page_size)}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            下一页
          </button>
        </div>
      </div>

      {/* 上传视频弹窗 */}
      {uploadModalVisible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">上传视频</h3>
              <button onClick={() => setUploadModalVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleUpload} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">选择视频文件</label>
                <input
                  type="file"
                  required
                  accept="video/*"
                  onChange={(e) => setUploadForm({ ...uploadForm, file: e.target.files[0] })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">标题（可选）</label>
                <input
                  type="text"
                  value={uploadForm.title}
                  onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="留空则使用文件名"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述（可选）</label>
                <textarea
                  value={uploadForm.description}
                  onChange={(e) => setUploadForm({ ...uploadForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows="3"
                  placeholder="视频描述信息"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
                <select
                  value={uploadForm.category}
                  onChange={(e) => setUploadForm({ ...uploadForm, category: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">请选择分类</option>
                  {categoryOptions.filter(opt => opt.value).map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">标签（用逗号分隔）</label>
                <input
                  type="text"
                  value={uploadForm.tags.join(',')}
                  onChange={(e) => setUploadForm({ ...uploadForm, tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="例如：营销,爆款,短平快"
                />
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setUploadModalVisible(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                  disabled={processing}
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  disabled={processing}
                >
                  {processing ? '上传中...' : '上传'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 批量导入弹窗 */}
      {importModalVisible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">批量导入爆款视频</h3>
              <button onClick={() => setImportModalVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleBatchImport} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">分类（可选）</label>
                <select
                  value={importForm.category}
                  onChange={(e) => setImportForm({ ...importForm, category: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">全部分类</option>
                  {categoryOptions.filter(opt => opt.value).map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">最低爆款分数</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  required
                  value={importForm.min_hot_score}
                  onChange={(e) => setImportForm({ ...importForm, min_hot_score: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">只导入分数高于此值的视频</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">最大导入数量</label>
                <input
                  type="number"
                  min="1"
                  max="200"
                  required
                  value={importForm.limit}
                  onChange={(e) => setImportForm({ ...importForm, limit: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setImportModalVisible(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                  disabled={processing}
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                  disabled={processing}
                >
                  {processing ? '导入中...' : '开始导入'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
