import { useState } from 'react'
import { X, Plus, Trash2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore.js'
import { createProject } from '../../services/project.js'

// 语音类型选项（火山引擎音色）
const VOICE_OPTIONS = [
  { value: 'zh_female_cancan_mars_bigtts', label: '温柔女声' },
  { value: 'zh_male_kailangxuezhang_uranus_bigtts', label: '清爽男声' },
]

export default function CreateProjectModal({ isOpen, onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [userPrompt, setUserPrompt] = useState('')
  const [voiceType, setVoiceType] = useState('zh_female_cancan_mars_bigtts')
  const [style, setStyle] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // 新增字段
  const [productUrl, setProductUrl] = useState('')
  const [targetAudience, setTargetAudience] = useState('')
  const [referenceImages, setReferenceImages] = useState([])
  const [keyPoints, setKeyPoints] = useState([])
  const [avoid, setAvoid] = useState([])

  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const setActiveView = useAppStore((state) => state.setActiveView)
  const bumpProjectListVersion = useAppStore((state) => state.bumpProjectListVersion)
  const clearDraftConversation = useAppStore((state) => state.clearDraftConversation)
  const parameters = useAppStore((state) => state.parameters)
  const updateParameters = useAppStore((state) => state.updateParameters)

  // 从 store 读取参数
  const targetDuration = parameters.target_duration
  const ragWeight = parameters.rag_weight

  // 关闭弹窗并重置表单
  const handleClose = () => {
    setTitle('')
    setDescription('')
    setUserPrompt('')
    setVoiceType('zh_female_cancan_mars_bigtts')
    setStyle('')
    setError('')
    setProductUrl('')
    setTargetAudience('')
    setReferenceImages([])
    setKeyPoints([])
    setAvoid([])
    onClose()
  }

  // 点击遮罩层关闭
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleClose()
    }
  }

  // 参考图片管理
  const addReferenceImage = () => {
    if (referenceImages.length < 5) {
      setReferenceImages([...referenceImages, ''])
    }
  }
  const updateReferenceImage = (index, value) => {
    const updated = [...referenceImages]
    updated[index] = value
    setReferenceImages(updated)
  }
  const removeReferenceImage = (index) => {
    setReferenceImages(referenceImages.filter((_, i) => i !== index))
  }

  // 动态列表管理（卖点/避免）
  const addListItem = (list, setList) => {
    setList([...list, ''])
  }
  const updateListItem = (list, setList, index, value) => {
    const updated = [...list]
    updated[index] = value
    setList(updated)
  }
  const removeListItem = (list, setList, index) => {
    setList(list.filter((_, i) => i !== index))
  }

  // 提交创建项目
  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!title.trim()) {
      setError('请输入项目标题')
      return
    }

    setLoading(true)
    try {
      const data = await createProject({
        title: title.trim(),
        description: description.trim() || undefined,
        user_prompt: userPrompt.trim() || undefined,
        product_url: productUrl.trim() || undefined,
        target_audience: targetAudience.trim() || undefined,
        reference_images: referenceImages.filter(img => img.trim()).length > 0
          ? referenceImages.filter(img => img.trim())
          : undefined,
        target_duration: Number(targetDuration) || 15,
        voice_type: voiceType,
        style: style.trim() || parameters.style || undefined,
        key_points: keyPoints.filter(p => p.trim()).length > 0
          ? keyPoints.filter(p => p.trim())
          : undefined,
        avoid: avoid.filter(a => a.trim()).length > 0
          ? avoid.filter(a => a.trim())
          : undefined,
        rag_weight: ragWeight || 0.3,
      })

      // 创建成功：切换到项目并关闭弹窗
      setActiveProjectId(data.id)
      clearDraftConversation()
      setActiveView('chat')
      bumpProjectListVersion()
      onCreated?.(data.id)
      handleClose()
    } catch (err) {
      setError(err.message || '创建失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div className="relative w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto rounded-2xl bg-[var(--bg-secondary)] border border-[var(--border-soft)] shadow-2xl">
        {/* 弹窗头部 */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-[var(--border-soft)] bg-[var(--bg-secondary)]">
          <h2 className="text-lg font-semibold text-white">新建项目</h2>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* 表单内容 */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* 错误信息 */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* === 基本信息 === */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-300 border-b border-gray-700 pb-2">基本信息</h3>

            {/* 标题 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                标题 <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                placeholder="请输入项目标题"
              />
            </div>

            {/* 描述 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">描述</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors resize-none"
                placeholder="简要描述项目内容"
              />
            </div>

            {/* 商品链接 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">商品链接</label>
              <input
                type="url"
                value={productUrl}
                onChange={(e) => setProductUrl(e.target.value)}
                className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                placeholder="粘贴淘宝/京东/拼多多/抖音商品链接，自动抓取商品信息"
              />
              <p className="mt-1 text-xs text-gray-500">支持淘宝、京东、拼多多、抖音平台</p>
            </div>
          </div>

          {/* === 创作意图 === */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-300 border-b border-gray-700 pb-2">创作意图</h3>

            {/* 创作意图 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">创作意图</label>
              <textarea
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                rows={3}
                className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors resize-none"
                placeholder="描述你想要的视频效果..."
              />
            </div>

            {/* 目标受众 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">目标受众</label>
              <input
                type="text"
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                placeholder="如：18-25岁年轻女性、宝妈群体、科技爱好者"
              />
            </div>

            {/* 卖点列表 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">重点卖点</label>
              <div className="space-y-2">
                {keyPoints.map((point, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={point}
                      onChange={(e) => updateListItem(keyPoints, setKeyPoints, index, e.target.value)}
                      className="flex-1 px-4 py-2 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                      placeholder={`卖点 ${index + 1}`}
                    />
                    <button
                      type="button"
                      onClick={() => removeListItem(keyPoints, setKeyPoints, index)}
                      className="p-2 text-gray-400 hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {keyPoints.length < 5 && (
                  <button
                    type="button"
                    onClick={() => addListItem(keyPoints, setKeyPoints)}
                    className="flex items-center gap-1 text-sm text-[#7C3AED] hover:text-[#6D28D9] transition-colors"
                  >
                    <Plus size={14} /> 添加卖点
                  </button>
                )}
              </div>
            </div>

            {/* 避免内容 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">避免内容</label>
              <div className="space-y-2">
                {avoid.map((item, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={item}
                      onChange={(e) => updateListItem(avoid, setAvoid, index, e.target.value)}
                      className="flex-1 px-4 py-2 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                      placeholder={`避免内容 ${index + 1}`}
                    />
                    <button
                      type="button"
                      onClick={() => removeListItem(avoid, setAvoid, index)}
                      className="p-2 text-gray-400 hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {avoid.length < 5 && (
                  <button
                    type="button"
                    onClick={() => addListItem(avoid, setAvoid)}
                    className="flex items-center gap-1 text-sm text-[#7C3AED] hover:text-[#6D28D9] transition-colors"
                  >
                    <Plus size={14} /> 添加避免内容
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* === 参考素材 === */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-300 border-b border-gray-700 pb-2">参考素材</h3>

            {/* 参考图片 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">参考图片（最多5张）</label>
              <div className="space-y-2">
                {referenceImages.map((url, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="url"
                      value={url}
                      onChange={(e) => updateReferenceImage(index, e.target.value)}
                      className="flex-1 px-4 py-2 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                      placeholder={`图片 URL ${index + 1}`}
                    />
                    <button
                      type="button"
                      onClick={() => removeReferenceImage(index)}
                      className="p-2 text-gray-400 hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {referenceImages.length < 5 && (
                  <button
                    type="button"
                    onClick={addReferenceImage}
                    className="flex items-center gap-1 text-sm text-[#7C3AED] hover:text-[#6D28D9] transition-colors"
                  >
                    <Plus size={14} /> 添加参考图片
                  </button>
                )}
              </div>
              <p className="mt-1 text-xs text-gray-500">提供参考图片可影响生成效果，第一张图会用于 RAG 检索</p>
            </div>
          </div>

          {/* === 生成参数 === */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-300 border-b border-gray-700 pb-2">生成参数</h3>

            {/* 目标时长 + 语音类型 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">目标时长</label>
                <div className="relative">
                  <input
                    type="number"
                    value={targetDuration}
                    onChange={(e) => {
                      const val = Number(e.target.value)
                      updateParameters({ target_duration: Math.max(12, Math.min(20, val)) })
                    }}
                    min={12}
                    max={20}
                    className="w-full px-4 py-2.5 pr-10 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-[var(--text-muted)]">
                    秒
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">有效范围：12-20 秒</p>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1.5">语音类型</label>
                <select
                  value={voiceType}
                  onChange={(e) => setVoiceType(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors appearance-none cursor-pointer"
                >
                  {VOICE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* 风格 */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">风格</label>
              <input
                type="text"
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                placeholder="如：清新、科技感、电影感"
              />
            </div>
          </div>

          {/* 按钮组 */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={handleClose}
              className="flex-1 py-2.5 border border-gray-700 text-gray-300 hover:bg-gray-700/50 rounded-lg text-sm font-medium transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
