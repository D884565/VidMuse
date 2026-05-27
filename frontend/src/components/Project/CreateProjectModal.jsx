import { useState } from 'react'
import { X } from 'lucide-react'
import { useAppStore } from '../../store/appStore.js'
import { createProject } from '../../services/project.js'

// 语音类型选项
const VOICE_OPTIONS = [
  { value: 'zh-CN-XiaoxiaoNeural', label: '晓晓' },
  { value: 'zh-CN-YunxiNeural', label: '云希' },
  { value: 'zh-CN-YunyangNeural', label: '云扬' },
]

export default function CreateProjectModal({ isOpen, onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [userPrompt, setUserPrompt] = useState('')
  const [voiceType, setVoiceType] = useState('zh-CN-XiaoxiaoNeural')
  const [style, setStyle] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const setActiveView = useAppStore((state) => state.setActiveView)
  const parameters = useAppStore((state) => state.parameters)
  const updateParameters = useAppStore((state) => state.updateParameters)

  // 从 store 读取 duration，避免本地默认值与 store 不一致
  const targetDuration = parameters.duration

  // 关闭弹窗并重置表单
  const handleClose = () => {
    setTitle('')
    setDescription('')
    setUserPrompt('')
    setVoiceType('zh-CN-XiaoxiaoNeural')
    setStyle('')
    setError('')
    onClose()
  }

  // 点击遮罩层关闭
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleClose()
    }
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
      // 从 store parameters 映射到后端字段
      const keyPoints = []
      if (parameters.aspectRatio) {
        keyPoints.push(`画幅比: ${parameters.aspectRatio}`)
      }

      const data = await createProject({
        title: title.trim(),
        description: description.trim() || undefined,
        user_prompt: userPrompt.trim() || undefined,
        target_duration: Number(targetDuration) || 30,
        voice_type: voiceType,
        style: style.trim() || parameters.quality || undefined,
        key_points: keyPoints.length > 0 ? keyPoints : undefined,
        rag_weight: 0.3,
      })

      // 创建成功：切换到项目并关闭弹窗
      setActiveProjectId(data.id)
      setActiveView('chat')
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
      <div className="relative w-full max-w-lg mx-4 rounded-2xl bg-[var(--bg-secondary)] border border-[var(--border-soft)] shadow-2xl">
        {/* 弹窗头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-soft)]">
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
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* 错误信息 */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

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

          {/* 创作意图 */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              创作意图
            </label>
            <textarea
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              rows={3}
              className="w-full px-4 py-2.5 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors resize-none"
              placeholder="描述你想要的视频效果..."
            />
          </div>

          {/* 目标时长 + 语音类型 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                目标时长
              </label>
              <div className="relative">
                <input
                  type="number"
                  value={targetDuration}
                  onChange={(e) => updateParameters({ duration: Number(e.target.value) })}
                  min={5}
                  max={300}
                  className="w-full px-4 py-2.5 pr-10 bg-[var(--bg-main)] border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-[#7C3AED] transition-colors"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-[var(--text-muted)]">
                  秒
                </span>
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                语音类型
              </label>
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
