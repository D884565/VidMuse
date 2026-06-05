import { useState, useRef, useCallback, useEffect } from 'react'
import { WandSparkles, Play, Image, Video, RotateCcw } from 'lucide-react'
import { useProjectEditor } from '../../hooks/useProjectEditor.js'
import { useAppStore } from '../../store/appStore.js'
import { downloadProjectVideo } from '../../services/project.js'
import SmartInput from '../Input/SmartInput.jsx'
import StageProgress from '../Workflow/StageProgress.jsx'
import MessageBubble from '../Chat/MessageBubble.jsx'
import MessageBlocks from '../Chat/MessageBlocks.jsx'
import TypingIndicator from '../Chat/TypingIndicator.jsx'

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content: `欢迎使用带货视频生成系统！我将帮助您一步步创建带货短视频：

1. 剧本创作 - 根据您的产品和需求生成分镜脚本
2. 分镜配图 - 为每个分镜生成精美的画面
3. 视频成片 - 将所有分镜合成为最终视频

请描述您想要推广的产品，或直接粘贴产品链接，我会为您开始创作。`,
  blocks: [
    {
      type: 'quick_actions',
      actions: [
        { label: '发个产品链接开始', hint: '粘贴淘宝/京东/抖音链接' },
        { label: '用文字描述产品', hint: '告诉我你想推什么' },
      ],
    },
  ],
}

const STATUS_MAP = { 0: '待处理', 1: '生成中', 2: '已完成', 3: '失败' }

export default function WorkbenchView() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const editor = useProjectEditor()
  const [selectedFrame, setSelectedFrame] = useState(null)
  const [rightPanel, setRightPanel] = useState('canvas') // 'canvas' | 'detail'
  const [chatWidth, setChatWidth] = useState(40) // percentage
  const [isDragging, setIsDragging] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [mobileTab, setMobileTab] = useState('chat')
  const containerRef = useRef(null)

  // 响应式检测
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  // 拖拽调整分栏
  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return
    const handleMouseMove = (e) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const pct = ((e.clientX - rect.left) / rect.width) * 100
      setChatWidth(Math.min(Math.max(pct, 25), 75))
    }
    const handleMouseUp = () => setIsDragging(false)
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  function handleActionComplete() {
    editor.reloadChat()
    editor.refetch()
  }

  function handleFrameSelect(frame) {
    setSelectedFrame(frame)
    setRightPanel('detail')
  }

  const displayMessages = activeProjectId
    ? editor.messages
    : [WELCOME_MESSAGE, ...editor.messages]

  // Chat Panel 内容
  const chatPanel = (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 pb-36 pt-4">
        <div className="space-y-4">
          {displayMessages.map((message, index) => (
            <MessageBubble
              key={message.id}
              message={message}
              index={index}
              onActionComplete={handleActionComplete}
            />
          ))}
          {editor.isTyping && <TypingIndicator />}
        </div>
      </div>
      <SmartInput onSend={editor.sendMessage} />
    </div>
  )

  // Canvas Panel 内容
  const canvasPanel = rightPanel === 'detail' && selectedFrame ? (
    <FrameDetailPanel
      frame={selectedFrame}
      project={editor.project}
      onBack={() => { setRightPanel('canvas'); setSelectedFrame(null) }}
      onEdit={editor.editFrame}
      onRegenerateImage={editor.regenerateFrameImage}
      onRegenerateVideo={editor.regenerateFrameVideo}
    />
  ) : (
    <div className="h-full overflow-y-auto p-4">
      {/* 视频预览（已完成项目） */}
      {editor.project?.workflow_stage === 'completed' && editor.videoUrl && (
        <div className="mb-4 rounded-xl border border-[#10b981]/25 bg-[#052e24]/50 p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold text-[#6ee7b7]">
            <Play size={16} />
            视频成片
          </div>
          <video src={editor.videoUrl} controls className="w-full rounded-lg bg-black" />
          <button
            type="button"
            onClick={() => downloadProjectVideo(activeProjectId)}
            className="mt-3 w-full rounded-lg bg-[#10b981]/20 py-2 text-xs text-[#6ee7b7] hover:bg-[#10b981]/30"
          >
            下载视频
          </button>
        </div>
      )}

      {/* 分镜卡片网格 */}
      {editor.frames?.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {editor.frames.map((frame) => (
            <FrameCard
              key={frame.id}
              frame={frame}
              onClick={() => handleFrameSelect(frame)}
            />
          ))}
        </div>
      )}

      {/* 空状态 */}
      {(!editor.frames || editor.frames.length === 0) && activeProjectId && (
        <div className="flex h-64 items-center justify-center text-sm text-[var(--text-muted)]">
          发送消息开始生成剧本...
        </div>
      )}
    </div>
  )

  // 移动端 Tab 模式
  if (isMobile) {
    return (
      <section className="flex h-screen flex-col overflow-hidden">
        <header className="border-b border-[var(--border-soft)] px-4 py-3">
          <div className="mb-2 flex items-center justify-between">
            <h1 className="m-0 text-lg font-semibold">对话式视频创作</h1>
            <div className="flex items-center gap-2 rounded-full border border-[var(--border-soft)] bg-[rgba(26,26,46,0.65)] px-3 py-1.5 text-xs text-[var(--text-muted)]">
              <WandSparkles size={14} className="text-[#38bdf8]" />
              助手在线
            </div>
          </div>
          {activeProjectId && <StageProgress project={editor.project} />}
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => setMobileTab('chat')}
              className={`flex-1 rounded-lg py-1.5 text-xs ${mobileTab === 'chat' ? 'bg-[var(--brand-soft)] text-white' : 'text-[var(--text-muted)]'}`}
            >
              对话
            </button>
            <button
              type="button"
              onClick={() => setMobileTab('canvas')}
              className={`flex-1 rounded-lg py-1.5 text-xs ${mobileTab === 'canvas' ? 'bg-[var(--brand-soft)] text-white' : 'text-[var(--text-muted)]'}`}
            >
              分镜
            </button>
          </div>
        </header>
        <div className="flex-1 overflow-hidden">
          {mobileTab === 'chat' ? chatPanel : canvasPanel}
        </div>
      </section>
    )
  }

  // 桌面端左右分栏
  return (
    <section className="flex h-screen flex-col overflow-hidden">
      <header className="border-b border-[var(--border-soft)] px-8 py-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h1 className="m-0 text-lg font-semibold">对话式视频创作</h1>
            <p className="m-0 text-xs text-[var(--text-muted)]">
              通过对话推进剧本、图片、视频三个阶段
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-[var(--border-soft)] bg-[rgba(26,26,46,0.65)] px-3 py-1.5 text-xs text-[var(--text-muted)]">
            <WandSparkles size={14} className="text-[#38bdf8]" />
            工作流助手在线
          </div>
        </div>
        {activeProjectId && <StageProgress project={editor.project} />}
      </header>

      <div ref={containerRef} className="flex flex-1 overflow-hidden">
        {/* Chat Panel */}
        <div
          className="flex flex-col overflow-hidden border-r border-[var(--border-soft)]"
          style={{ width: `${chatWidth}%` }}
        >
          {chatPanel}
        </div>

        {/* Drag handle */}
        <div
          className={`w-1 cursor-col-resize hover:bg-[#38bdf8]/30 ${isDragging ? 'bg-[#38bdf8]/40' : 'bg-transparent'}`}
          onMouseDown={handleMouseDown}
        />

        {/* Canvas Panel */}
        <div className="flex-1 overflow-hidden">
          {canvasPanel}
        </div>
      </div>
    </section>
  )
}

/** 分镜卡片 */
function FrameCard({ frame, onClick }) {
  const status = STATUS_MAP[frame.status] || '未知'
  const statusColor = {
    '待处理': 'text-[var(--text-muted)]',
    '生成中': 'text-[#38bdf8]',
    '已完成': 'text-[#10b981]',
    '失败': 'text-red-400',
  }[status] || 'text-[var(--text-muted)]'

  return (
    <button
      type="button"
      onClick={onClick}
      className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.04] text-left transition-all hover:border-[#38bdf8]/40 hover:bg-white/[0.06]"
    >
      {frame.image_url ? (
        <img src={frame.image_url} alt={`分镜 ${frame.sequence}`} className="aspect-video w-full object-cover" />
      ) : (
        <div className="flex aspect-video w-full items-center justify-center bg-white/[0.02]">
          <Image size={24} className="text-white/20" />
        </div>
      )}
      <div className="p-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-white">#{frame.sequence}</span>
          <span className={`text-xs ${statusColor}`}>{status}</span>
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-[var(--text-muted)]">
          {frame.description || '无描述'}
        </p>
        <div className="mt-1 text-xs text-[var(--text-muted)]">
          {frame.duration ? `${frame.duration}s` : ''}
        </div>
        {frame.dirty ? (
          <span className="mt-1 inline-block rounded-full bg-[#f59e0b]/20 px-2 py-0.5 text-[10px] text-[#fbbf24]">
            需重新确认
          </span>
        ) : null}
      </div>
    </button>
  )
}

/** 分镜详情面板 */
function FrameDetailPanel({ frame, project, onBack, onEdit, onRegenerateImage, onRegenerateVideo }) {
  const [fields, setFields] = useState({
    description: frame.description || '',
    narration: frame.narration || '',
    image_prompt: frame.image_prompt || '',
    video_prompt: frame.video_prompt || '',
    duration: frame.duration || 3,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function updateField(key, value) {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      await onEdit(frame.id, fields)
    } catch (err) {
      setError(err.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleRegenImage() {
    setSaving(true)
    setError('')
    try {
      await onRegenerateImage(frame.id, '')
    } catch (err) {
      setError(err.message || '操作失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleRegenVideo() {
    setSaving(true)
    setError('')
    try {
      await onRegenerateVideo(frame.id, '')
    } catch (err) {
      setError(err.message || '操作失败')
    } finally {
      setSaving(false)
    }
  }

  const isCompleted = project?.workflow_stage === 'completed'

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-[var(--border-soft)] px-4 py-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg p-1 text-[var(--text-muted)] hover:bg-white/10"
        >
          <RotateCcw size={16} />
        </button>
        <span className="text-sm font-semibold text-white">分镜 #{frame.sequence}</span>
        {frame.dirty ? (
          <span className="rounded-full bg-[#f59e0b]/20 px-2 py-0.5 text-[10px] text-[#fbbf24]">
            需重新确认
          </span>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {/* 图片预览 */}
        {frame.image_url && (
          <div className="mb-4 overflow-hidden rounded-xl border border-white/10">
            <img src={frame.image_url} alt={`分镜 ${frame.sequence}`} className="w-full object-cover" />
          </div>
        )}

        {/* 编辑字段 */}
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-[var(--text-muted)]">画面描述</label>
            <textarea
              value={fields.description}
              onChange={(e) => updateField('description', e.target.value)}
              rows={3}
              className="w-full resize-none rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white outline-none focus:border-[#38bdf8]/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--text-muted)]">旁白</label>
            <textarea
              value={fields.narration}
              onChange={(e) => updateField('narration', e.target.value)}
              rows={2}
              className="w-full resize-none rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white outline-none focus:border-[#38bdf8]/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--text-muted)]">图片提示词</label>
            <input
              type="text"
              value={fields.image_prompt}
              onChange={(e) => updateField('image_prompt', e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white outline-none focus:border-[#38bdf8]/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--text-muted)]">视频提示词</label>
            <input
              type="text"
              value={fields.video_prompt}
              onChange={(e) => updateField('video_prompt', e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white outline-none focus:border-[#38bdf8]/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--text-muted)]">时长(秒)</label>
            <input
              type="number"
              step="0.5"
              min="0.5"
              max="10"
              value={fields.duration}
              onChange={(e) => updateField('duration', e.target.value)}
              className="w-24 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white outline-none focus:border-[#38bdf8]/50"
            />
          </div>
        </div>

        {/* 已完成项目提示 */}
        {isCompleted && (
          <div className="mt-4 rounded-lg border border-[#f59e0b]/25 bg-[#3b2505]/20 p-3 text-xs text-[#fbbf24]">
            修改将重新生成该分镜的图片/视频，预计耗时30-60秒。
          </div>
        )}

        {error && <div className="mt-3 text-xs text-red-300">{error}</div>}
      </div>

      {/* 操作按钮 */}
      <div className="border-t border-[var(--border-soft)] p-4">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={saving}
            onClick={handleSave}
            className="flex-1 rounded-lg bg-[#38bdf8]/20 py-2 text-xs text-[#7dd3fc] hover:bg-[#38bdf8]/30 disabled:opacity-50"
          >
            {saving ? '保存中...' : '保存修改'}
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={handleRegenImage}
            className="flex items-center justify-center gap-1 rounded-lg bg-[#a78bfa]/15 px-3 py-2 text-xs text-[#c4b5fd] hover:bg-[#a78bfa]/25 disabled:opacity-50"
          >
            <Image size={14} />
            重生成图片
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={handleRegenVideo}
            className="flex items-center justify-center gap-1 rounded-lg bg-[#10b981]/15 px-3 py-2 text-xs text-[#6ee7b7] hover:bg-[#10b981]/25 disabled:opacity-50"
          >
            <Video size={14} />
            重生成视频
          </button>
        </div>
      </div>
    </div>
  )
}
