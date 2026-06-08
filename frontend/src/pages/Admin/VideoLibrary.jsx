import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Upload, Play, RefreshCw, Import, FileCode } from 'lucide-react'
import PageContainer from '../../components/Admin/Layout/PageContainer'
import Table from '../../components/Admin/Common/Table'
import { getVideoList, deleteVideo, triggerVideoParsing, batchImportHotVideos, uploadVideo, getCategoryTree } from '../../services/admin'

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'title', title: '视频标题' },
  {
    key: 'category',
    title: '分类',
    render: (category, row) => {
      // 如果有category名称直接显示，否则通过category_id查找
      if (category) {
        return (
          <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            {category}
          </span>
        )
      }
      if (row.category_id) {
        const categoryName = getCategoryNameById(row.category_id)
        return (
          <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            {categoryName || '未知分类'}
          </span>
        )
      }
      return (
        <span className="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          未分类
        </span>
      )
    }
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
    key: 'parsing_status',
    title: '状态',
    render: (parsing_status) => {
      const statusMap = {
        'pending': '待处理',
        'running': '处理中',
        'completed': '已完成',
        'failed': '失败'
      }
      const classMap = {
        'pending': 'bg-yellow-100 text-yellow-800',
        'running': 'bg-blue-100 text-blue-800',
        'completed': 'bg-green-100 text-green-800',
        'failed': 'bg-red-100 text-red-800'
      }
      return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${classMap[parsing_status] || 'bg-gray-100 text-gray-800'}`}>
          {statusMap[parsing_status] || '未知'}
        </span>
      )
    }
  },
  { key: 'duration', title: '时长(秒)' },
  { key: 'file_size', title: '文件大小' },
  { key: 'created_by', title: '创建人' },
  { key: 'created_at', title: '创建时间' },
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
  const [categoryTree, setCategoryTree] = useState([])
  const [categoryLoading, setCategoryLoading] = useState(false)
  const [filters, setFilters] = useState({
    category_id: '',
    min_hot_score: '',
    source_type: '',
    keyword: '',
    status: '',
    page: 1,
    page_size: 20,
  })
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: 20 })
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [importModalVisible, setImportModalVisible] = useState(false)
  const [playModalVisible, setPlayModalVisible] = useState(false)
  const [currentPlayingVideo, setCurrentPlayingVideo] = useState(null)
  const [parseModalVisible, setParseModalVisible] = useState(false)
  const [currentParseData, setCurrentParseData] = useState(null)
  const [uploadForm, setUploadForm] = useState({
    file: null,
    title: '',
    description: '',
    category_id: '',
    tags: [],
    trigger_ai_parse: true,
  })
  const [importForm, setImportForm] = useState({
    category_id: '',
    min_hot_score: 80,
    limit: 50,
  })
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    fetchVideos()
    fetchCategoryTree()
  }, [filters])

  const fetchCategoryTree = async () => {
    try {
      setCategoryLoading(true)
      const data = await getCategoryTree()
      setCategoryTree(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('获取分类树失败:', error)
      setCategoryTree([])
    } finally {
      setCategoryLoading(false)
    }
  }

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
      formData.append('trigger_ai_parse', uploadForm.trigger_ai_parse)
      uploadForm.tags.forEach(tag => formData.append('tags[]', tag))

      // 调用上传接口
      await uploadVideo(formData)

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

  // 递归渲染分类选项
  const renderCategoryOptions = (categories, level = 0, allowSelectAllLevels = false) => {
    const options = []
    const indent = ' '.repeat(level * 4) // 使用空格缩进显示层级

    categories.forEach(category => {
      // 对于上传弹窗，只允许选择三级分类；对于筛选和批量导入，可以选择任意层级
      const isDisabled = !allowSelectAllLevels && category.level < 3

      options.push(
        <option
          key={category.id}
          value={category.id}
          disabled={isDisabled}
          className={isDisabled ? 'text-gray-400' : ''}
        >
          {indent}{category.name}{isDisabled ? ' (不可选)' : ''}
        </option>
      )

      // 递归渲染子分类
      if (category.children && category.children.length > 0) {
        options.push(...renderCategoryOptions(category.children, level + 1, allowSelectAllLevels))
      }
    })

    return options
  }

  // 根据分类id获取分类名称
  const getCategoryNameById = (categoryId, categories = categoryTree) => {
    if (!categoryId) return null
    const id = parseInt(categoryId)
    for (const category of categories) {
      if (category.id === id) {
        return category.name
      }
      if (category.children && category.children.length > 0) {
        const name = getCategoryNameById(categoryId, category.children)
        if (name) return name
      }
    }
    return null
  }

  const handlePlay = (video) => {
    setCurrentPlayingVideo(video)
    setPlayModalVisible(true)
  }

  const handleViewParseResult = (video) => {
    setCurrentParseData(video)
    setParseModalVisible(true)
  }

  const actions = (row) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={() => handlePlay(row)}
        className="p-1 text-blue-600 hover:text-blue-800"
        title="播放"
      >
        <Play size={16} />
      </button>
      <button
        onClick={() => handleViewParseResult(row)}
        className={`p-1 ${row.parsed_data ? 'text-indigo-600 hover:text-indigo-800' : 'text-gray-400 cursor-not-allowed'}`}
        title={row.parsed_data ? '查看AI解析结果' : '暂无解析结果'}
        disabled={!row.parsed_data}
      >
        <FileCode size={16} />
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
            value={filters.category_id}
            onChange={(e) => handleFilterChange('category_id', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={categoryLoading}
          >
            <option value="">全部分类</option>
            {categoryLoading ? (
              <option value="" disabled>加载中...</option>
            ) : (
              renderCategoryOptions(categoryTree, 0, true)
            )}
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
                  value={uploadForm.category_id}
                  onChange={(e) => setUploadForm({ ...uploadForm, category_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={categoryLoading}
                >
                  <option value="">请选择三级分类</option>
                  {categoryLoading ? (
                    <option value="" disabled>加载中...</option>
                  ) : (
                    renderCategoryOptions(categoryTree, 0, false)
                  )}
                </select>
                <p className="text-xs text-gray-500 mt-1">请选择三级分类，一级和二级分类不可选</p>
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
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="trigger_ai_parse"
                  checked={uploadForm.trigger_ai_parse}
                  onChange={(e) => setUploadForm({ ...uploadForm, trigger_ai_parse: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="trigger_ai_parse" className="text-sm font-medium text-gray-700">
                  上传后立即触发AI解析
                </label>
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
                  value={importForm.category_id}
                  onChange={(e) => setImportForm({ ...importForm, category_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={categoryLoading}
                >
                  <option value="">不指定分类</option>
                  {categoryLoading ? (
                    <option value="" disabled>加载中...</option>
                  ) : (
                    renderCategoryOptions(categoryTree, 0, false)
                  )}
                </select>
                <p className="text-xs text-gray-500 mt-1">可选，请选择三级分类，导入的视频将归属到该分类下</p>
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

      {/* 视频播放弹窗 */}
      {playModalVisible && currentPlayingVideo && (
        <div className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold truncate">
                {currentPlayingVideo.title || '视频播放'}
              </h3>
              <button
                onClick={() => setPlayModalVisible(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 p-4 bg-black overflow-auto">
              <video
                src={currentPlayingVideo.url}
                controls
                autoPlay
                className="w-full h-full max-h-[70vh] object-contain"
                poster={currentPlayingVideo.cover_url}
                onError={(e) => {
                  console.error('视频加载失败:', e)
                  alert('视频加载失败，请检查视频URL是否有效')
                }}
              >
                您的浏览器不支持视频播放。
              </video>
            </div>
            <div className="p-4 border-t bg-gray-50">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium text-gray-600">视频ID：</span>
                  <span className="text-gray-800">{currentPlayingVideo.id}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">分类：</span>
                  <span className="text-gray-800">{currentPlayingVideo.category || '未分类'}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">大小：</span>
                  <span className="text-gray-800">
                    {currentPlayingVideo.file_size
                      ? `${(currentPlayingVideo.file_size / (1024 * 1024)).toFixed(2)} MB`
                      : '未知'}
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-600">时长：</span>
                  <span className="text-gray-800">
                    {currentPlayingVideo.duration
                      ? `${currentPlayingVideo.duration} 秒`
                      : '未知'}
                  </span>
                </div>
              </div>
              {currentPlayingVideo.description && (
                <div className="mt-3 text-sm">
                  <span className="font-medium text-gray-600">描述：</span>
                  <p className="text-gray-800 mt-1">{currentPlayingVideo.description}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* AI解析结果弹窗 */}
      {parseModalVisible && currentParseData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold">
                AI解析结果 - {currentParseData.title || `视频 #${currentParseData.id}`}
              </h3>
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  currentParseData.parsing_status === 'completed' ? 'bg-green-100 text-green-800' :
                  currentParseData.parsing_status === 'failed' ? 'bg-red-100 text-red-800' :
                  currentParseData.parsing_status === 'running' ? 'bg-blue-100 text-blue-800' :
                  'bg-yellow-100 text-yellow-800'
                }`}>
                  {currentParseData.parsing_status === 'completed' ? '解析成功' :
                   currentParseData.parsing_status === 'failed' ? '解析失败' :
                   currentParseData.parsing_status === 'running' ? '解析中' : '待解析'}
                </span>
                <button
                  onClick={() => setParseModalVisible(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {currentParseData.parsing_status === 'failed' && currentParseData.parsing_error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <h4 className="text-sm font-medium text-red-800 mb-1">解析错误信息：</h4>
                  <pre className="text-xs text-red-700 whitespace-pre-wrap">{currentParseData.parsing_error}</pre>
                </div>
              )}

              {currentParseData.parsed_data ? (
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="text-sm font-medium text-gray-700">结构化解析数据：</h4>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(JSON.stringify(currentParseData.parsed_data, null, 2))
                        alert('解析结果已复制到剪贴板')
                      }}
                      className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
                    >
                      复制JSON
                    </button>
                  </div>
                  <pre className="bg-gray-50 p-4 rounded-lg border border-gray-200 text-xs overflow-auto max-h-[60vh]">
                    {JSON.stringify(currentParseData.parsed_data, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <FileCode size={48} className="mx-auto mb-4 text-gray-300" />
                  <p>暂无AI解析结果</p>
                  {currentParseData.parsing_status === 'pending' && (
                    <p className="text-sm mt-2 text-yellow-600">视频等待解析中，请稍后再试</p>
                  )}
                  {currentParseData.parsing_status === 'running' && (
                    <p className="text-sm mt-2 text-blue-600">视频正在解析中，请稍后刷新查看</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
