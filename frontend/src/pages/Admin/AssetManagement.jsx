import { useState, useEffect } from 'react'
import { Eye, Trash2, Upload, RefreshCw, Play } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import { getAssetList, deleteAsset, parseAsset, getParsingProgress, retryParsing } from '../../services/admin'

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'title', title: '标题' },
  {
    key: 'type',
    title: '类型',
    render: (type) => {
      const typeMap = { 1: '图片', 2: '视频', 3: '音频' }
      const classMap = {
        1: 'bg-green-100 text-green-800',
        2: 'bg-blue-100 text-blue-800',
        3: 'bg-purple-100 text-purple-800'
      }
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${classMap[type] || 'bg-gray-100 text-gray-800'}`}>
          {typeMap[type] || '未知'}
        </span>
      )
    }
  },
  { key: 'username', title: '上传用户' },
  {
    key: 'source_type',
    title: '来源',
    render: (source) => {
      const sourceMap = { 0: '用户上传', 1: 'AI生成', 2: '系统预置', 3: '购买' }
      return <span>{sourceMap[source] || source}</span>
    }
  },
  {
    key: 'status',
    title: '解析状态',
    render: (status) => {
      const statusMap = { 0: '待解析', 1: '解析中', 2: '解析成功', 3: '解析失败' }
      const classMap = {
        0: 'bg-yellow-100 text-yellow-800',
        1: 'bg-blue-100 text-blue-800',
        2: 'bg-green-100 text-green-800',
        3: 'bg-red-100 text-red-800'
      }
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${classMap[status] || 'bg-gray-100 text-gray-800'}`}>
          {statusMap[status] || '未知'}
        </span>
      )
    }
  },
  { key: 'size', title: '文件大小' },
  { key: 'duration', title: '时长(秒)' },
  { key: 'createdAt', title: '上传时间' },
]

const typeOptions = [
  { value: '', label: '全部类型' },
  { value: 1, label: '图片' },
  { value: 2, label: '视频' },
  { value: 3, label: '音频' },
]

const sourceOptions = [
  { value: '', label: '全部来源' },
  { value: 0, label: '用户上传' },
  { value: 1, label: 'AI生成' },
  { value: 2, label: '系统预置' },
]

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 0, label: '待解析' },
  { value: 1, label: '解析中' },
  { value: 2, label: '解析成功' },
  { value: 3, label: '解析失败' },
]

export default function AssetManagement() {
  const [loading, setLoading] = useState(true)
  const [assets, setAssets] = useState([])
  const [filters, setFilters] = useState({
    type: '',
    source_type: '',
    status: '',
    keyword: '',
    page: 1,
    page_size: 20,
  })
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: 20 })
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [uploadForm, setUploadForm] = useState({
    file: null,
    type: 2,
    title: '',
    source_type: 2,
    skip_ai_analysis: true,
  })
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    fetchAssets()
  }, [filters])

  const fetchAssets = async () => {
    try {
      setLoading(true)
      const params = Object.fromEntries(
        Object.entries(filters).filter(([_, v]) => v !== '' && v != null)
      )
      const data = await getAssetList(params)
      setAssets(Array.isArray(data) ? data : data?.list || [])
      setPagination({
        total: data?.total || data?.length || 0,
        page: params.page || 1,
        page_size: params.page_size || 20,
      })
    } catch (error) {
      console.error('获取资产列表失败:', error)
      setAssets([])
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }))
  }

  const handleDelete = async (assetId) => {
    if (window.confirm('确定要删除这个资产吗？删除后无法恢复！')) {
      try {
        await deleteAsset(assetId)
        fetchAssets()
      } catch (error) {
        console.error('删除资产失败:', error)
        alert('删除失败，请重试')
      }
    }
  }

  const handleParse = async (assetId, force = false) => {
    try {
      await parseAsset(assetId, force)
      alert('解析任务已启动，请稍后刷新查看状态')
    } catch (error) {
      console.error('触发解析失败:', error)
      alert('操作失败，请重试')
    }
  }

  const handleRetry = async (assetId) => {
    try {
      await retryParsing(assetId)
      alert('重试解析任务已启动')
    } catch (error) {
      console.error('重试解析失败:', error)
      alert('操作失败，请重试')
    }
  }

  const checkProgress = async (assetId) => {
    try {
      const progress = await getParsingProgress(assetId)
      alert(`解析进度：${progress.percent || 0}%\n状态：${progress.message || '处理中'}`)
    } catch (error) {
      console.error('获取进度失败:', error)
      alert('获取进度失败，请重试')
    }
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!uploadForm.file) {
      alert('请选择文件')
      return
    }

    try {
      setUploading(true)
      const formData = new FormData()
      formData.append('file', uploadForm.file)
      formData.append('type', uploadForm.type)
      formData.append('title', uploadForm.title || uploadForm.file.name)
      formData.append('source_type', uploadForm.source_type)
      formData.append('skip_ai_analysis', uploadForm.skip_ai_analysis)

      // 调用上传接口
      // await uploadInternalAsset(formData)

      alert('上传成功！')
      setUploadModalVisible(false)
      setUploadForm({ file: null, type: 2, title: '', source_type: 2, skip_ai_analysis: true })
      fetchAssets()
    } catch (error) {
      console.error('上传失败:', error)
      alert('上传失败，请重试')
    } finally {
      setUploading(false)
    }
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        className="p-1 text-blue-600 hover:text-blue-800"
        title="预览"
      >
        <Play size={16} />
      </button>
      <button
        className="p-1 text-purple-600 hover:text-purple-800"
        title="查看详情"
      >
        <Eye size={16} />
      </button>
      {row.status === 0 && (
        <button
          onClick={() => handleParse(row.id)}
          className="p-1 text-green-600 hover:text-green-800"
          title="开始解析"
        >
          <RefreshCw size={16} />
        </button>
      )}
      {row.status === 3 && (
        <button
          onClick={() => handleRetry(row.id)}
          className="p-1 text-yellow-600 hover:text-yellow-800"
          title="重试解析"
        >
          <RefreshCw size={16} />
        </button>
      )}
      {(row.status === 1 || row.status === 0) && (
        <button
          onClick={() => checkProgress(row.id)}
          className="p-1 text-blue-600 hover:text-blue-800"
          title="查看进度"
        >
          <RefreshCw size={16} />
        </button>
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

  return (
    <PageContainer
      title="资产管理"
      actions={
        <button
          onClick={() => setUploadModalVisible(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Upload size={20} />
          <span>上传资产</span>
        </button>
      }
    >
      {/* 筛选栏 */}
      <div className="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">资源类型</label>
          <select
            value={filters.type}
            onChange={(e) => handleFilterChange('type', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {typeOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">来源类型</label>
          <select
            value={filters.source_type}
            onChange={(e) => handleFilterChange('source_type', e.target.value ? parseInt(e.target.value) : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {sourceOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">解析状态</label>
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
            placeholder="搜索标题/文件名"
            value={filters.keyword}
            onChange={(e) => handleFilterChange('keyword', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            onKeyDown={(e) => e.key === 'Enter' && fetchAssets()}
          />
        </div>
      </div>

      {/* 资产列表 */}
      <Table
        columns={columns}
        data={assets}
        actions={actions}
        loading={loading}
      />

      {/* 分页信息 */}
      <div className="mt-4 flex items-center justify-between text-sm text-gray-700">
        <div>
          共 {pagination.total} 条记录，第 {pagination.page} 页 / 共 {Math.ceil(pagination.total / pagination.page_size)} 页
        </div>
        <div className="space-x-2">
          <button
            onClick={() => handleFilterChange('page', Math.max(1, pagination.page - 1))}
            disabled={pagination.page <= 1}
            className="px-3 py-1 border border-gray-300 rounded disabled:opacity-50 hover:bg-gray-50 text-gray-700"
          >
            上一页
          </button>
          <button
            onClick={() => handleFilterChange('page', pagination.page + 1)}
            disabled={pagination.page >= Math.ceil(pagination.total / pagination.page_size)}
            className="px-3 py-1 border border-gray-300 rounded disabled:opacity-50 hover:bg-gray-50 text-gray-700"
          >
            下一页
          </button>
        </div>
      </div>

      {/* 上传弹窗 */}
      {uploadModalVisible && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold">上传内部资产</h3>
              <button onClick={() => setUploadModalVisible(false)} className="text-gray-400 hover:text-gray-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleUpload} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">选择文件</label>
                <input
                  type="file"
                  required
                  onChange={(e) => setUploadForm({ ...uploadForm, file: e.target.files[0] })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  accept="image/*,video/*,audio/*"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">资源类型</label>
                <select
                  value={uploadForm.type}
                  onChange={(e) => setUploadForm({ ...uploadForm, type: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={1}>图片</option>
                  <option value={2}>视频</option>
                  <option value={3}>音频</option>
                </select>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">来源类型</label>
                <select
                  value={uploadForm.source_type}
                  onChange={(e) => setUploadForm({ ...uploadForm, source_type: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={0}>用户上传</option>
                  <option value={1}>AI生成</option>
                  <option value={2}>系统预置</option>
                  <option value={3}>其他</option>
                </select>
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="skip_analysis"
                  checked={uploadForm.skip_ai_analysis}
                  onChange={(e) => setUploadForm({ ...uploadForm, skip_ai_analysis: e.target.checked })}
                  className="mr-2"
                />
                <label htmlFor="skip_analysis" className="text-sm text-gray-700">跳过AI特征分析</label>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setUploadModalVisible(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                  disabled={uploading}
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  disabled={uploading}
                >
                  {uploading ? '上传中...' : '上传'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
