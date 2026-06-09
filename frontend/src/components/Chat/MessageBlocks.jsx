import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Play, RefreshCw, XCircle } from 'lucide-react'
import { getGenerationTask } from '../../services/project.js'
import { useAppStore } from '../../store/appStore.js'
import { formatVideoStyle } from '../../utils/videoStyle.js'

const TASK_POLL_INTERVAL_MS = 2000
const SUCCESS_STATUSES = new Set(['confirmed', 'completed', 'complete', 'success', 'succeeded', 'done'])
const FAILURE_STATUSES = new Set(['failed', 'failure', 'error', 'cancelled', 'canceled'])
const TERMINAL_STATUSES = new Set([...SUCCESS_STATUSES, ...FAILURE_STATUSES])

/** 格式化时长为整数秒显示（如 5s） */
function formatDurationLabel(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return '0s'
  return `${Math.round(numeric)}s`
}

function getProgressCardTone(status) {
  const normalizedStatus = String(status || 'running').toLowerCase()
  if (SUCCESS_STATUSES.has(normalizedStatus)) {
    return {
      wrapper: 'border-[#10b981]/25 bg-[#052e24]/45',
      text: 'text-[#6ee7b7]',
      icon: CheckCircle2,
      spin: false,
    }
  }
  if (FAILURE_STATUSES.has(normalizedStatus)) {
    return {
      wrapper: 'border-[#ef4444]/25 bg-[#3f1111]/40',
      text: 'text-[#fca5a5]',
      icon: XCircle,
      spin: false,
    }
  }
  return {
    wrapper: 'border-[#f59e0b]/25 bg-[#3b2505]/35',
    text: 'text-[#fbbf24]',
    icon: RefreshCw,
    spin: true,
  }
}

export default function MessageBlocks({ blocks = [], onActionComplete }) {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  void activeProjectId

  if (!blocks?.length) return null

  return (
    <div className="mt-4 space-y-4">
      {blocks.map((block, index) => {
        if (block.type === 'script_summary') return <ScriptSummary key={index} block={block} />
        if (block.type === 'storyboard_table') return <StoryboardTable key={index} block={block} />
        if (block.type === 'image_grid') return <ImageGrid key={index} block={block} />
        if (block.type === 'video_card') return <VideoCard key={index} block={block} />
        if (block.type === 'progress_card') return <ProgressCard key={index} block={block} onActionComplete={onActionComplete} />
        if (block.type === 'follow_up') return <FollowUp key={index} block={block} />
        if (block.type === 'asset_grid') return <AssetGrid key={index} block={block} />
        if (block.type === 'product_card') return <ProductCard key={index} block={block} />
        if (block.type === 'quick_actions') return <QuickActions key={index} block={block} />
        if (block.type === 'frame_editor') return <FrameEditor key={index} block={block} />
        if (block.type === 'confirmation_preview') return <ConfirmationPreview key={index} block={block} />
        return null
      })}
    </div>
  )
}

function FollowUp({ block }) {
  return (
    <div className="rounded-xl border border-[#38bdf8]/20 bg-[#082f49]/25 px-4 py-3 text-sm leading-relaxed text-slate-100">
      {block.message}
    </div>
  )
}

function ScriptSummary({ block }) {
  return (
    <div className="rounded-xl border border-[#38bdf8]/25 bg-[#0f2a3a]/45 p-4">
      <div className="text-sm font-semibold text-[#7dd3fc]">{block.title || '剧本方案'}</div>
      <div className="mt-2 grid gap-2 text-xs text-slate-200 sm:grid-cols-2">
        <p className="m-0">主题：{block.theme}</p>
        <p className="m-0">风格：{formatVideoStyle(block.style)}</p>
        <p className="m-0">分镜数：{block.frame_count}</p>
        <p className="m-0">总时长：{formatDurationLabel(block.total_duration)}</p>
      </div>
      <p className="mb-0 mt-3 text-xs text-[var(--text-muted)]">{block.visual_plan}</p>
    </div>
  )
}

function StoryboardTable({ block }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[rgba(148,163,184,0.14)]">
      <div className="grid grid-cols-[64px_80px_1fr] bg-white/5 px-3 py-2 text-xs text-[var(--text-muted)]">
        <span>分镜</span>
        <span>时长</span>
        <span>画面与旁白</span>
      </div>
      {(block.frames || []).map((frame) => (
        <div key={frame.id || frame.sequence} className="grid grid-cols-[64px_80px_1fr] gap-2 border-t border-white/5 px-3 py-3 text-xs">
          <span className="font-semibold text-white">#{frame.sequence}</span>
          <span>{formatDurationLabel(frame.duration)}</span>
          <div>
            <p className="m-0 text-white">{frame.scene}</p>
            <p className="mb-0 mt-1 text-[var(--text-muted)]">{frame.narration}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function ImageGrid({ block }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {(block.images || []).map((image) => (
        <div key={image.frame_id || image.sequence} className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.04]">
          {image.url ? (
            <img src={image.url} alt={`分镜 ${image.sequence}`} className="aspect-[9/16] w-full object-cover" />
          ) : (
            <div className="grid aspect-[9/16] place-items-center text-xs text-[var(--text-muted)]">待生成</div>
          )}
          <div className="p-3 text-xs">
            <div className="font-semibold text-white">分镜 {image.sequence}</div>
            <div className="mt-1 line-clamp-2 text-[var(--text-muted)]">{image.description}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function VideoCard({ block }) {
  return (
    <div className="inline-block max-w-[280px] rounded-xl border border-[#10b981]/25 bg-[#052e24]/50 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-[#6ee7b7]">
        <Play size={14} />
        视频成片
      </div>
      {block.video_url ? (
        <video src={block.video_url} controls className="aspect-[9/16] w-full rounded-lg bg-black object-cover" />
      ) : (
        <div className="flex aspect-[9/16] items-center justify-center rounded-lg bg-black/40 text-xs text-[var(--text-muted)]">视频生成中...</div>
      )}
    </div>
  )
}

function ProgressCard({ block, onActionComplete }) {
  const initialStatus = String(block.status || 'running').toLowerCase()
  const [taskStatus, setTaskStatus] = useState(initialStatus)
  const notifiedRef = useRef(SUCCESS_STATUSES.has(initialStatus))
  const effectiveStatus = taskStatus || initialStatus
  const tone = getProgressCardTone(effectiveStatus)
  const Icon = tone.icon

  useEffect(() => {
    setTaskStatus(initialStatus)
    notifiedRef.current = SUCCESS_STATUSES.has(initialStatus)
  }, [block.task_id, initialStatus])

  useEffect(() => {
    if (!block.task_id || TERMINAL_STATUSES.has(taskStatus)) return undefined

    let cancelled = false
    const pollTask = async () => {
      try {
        const task = await getGenerationTask(block.task_id)
        const nextStatus = String(task?.status || '').toLowerCase()
        if (!cancelled && nextStatus) {
          setTaskStatus(nextStatus)
        }
      } catch (error) {
        console.warn('Failed to poll generation task', error)
      }
    }

    pollTask()
    const timer = setInterval(pollTask, TASK_POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [block.task_id, taskStatus])

  useEffect(() => {
    if (!SUCCESS_STATUSES.has(effectiveStatus) || notifiedRef.current) return
    notifiedRef.current = true
    onActionComplete?.()
  }, [effectiveStatus, onActionComplete])

  return (
    <div className={`rounded-xl border ${tone.wrapper} p-4 text-sm`}>
      <div className={`flex items-center gap-2 ${tone.text}`}>
        <Icon size={15} className={tone.spin ? 'animate-spin' : undefined} />
        {block.message}
      </div>
    </div>
  )
}

function AssetGrid({ block }) {
  const items = block.items || block.assets || []
  if (!items.length) return null
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {items.map((asset, index) => (
        <div key={asset.url || index} className="overflow-hidden rounded-lg border border-white/10 bg-white/[0.04]">
          {asset.url ? (
            <img src={asset.url} alt={asset.title || '素材'} className="aspect-square w-full object-cover" />
          ) : (
            <div className="grid aspect-square place-items-center text-xs text-[var(--text-muted)]">{asset.title || '素材'}</div>
          )}
          {asset.title && (
            <div className="truncate px-2 py-1.5 text-xs text-[var(--text-muted)]">{asset.title}</div>
          )}
        </div>
      ))}
    </div>
  )
}

function ProductCard({ block }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-[#a78bfa]/25 bg-[#1a0f2e]/50 p-4">
      {block.image_url ? (
        <img src={block.image_url} alt={block.title || '商品'} className="h-16 w-16 shrink-0 rounded-lg object-cover" />
      ) : (
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-lg bg-white/5 text-xs text-[var(--text-muted)]">商品</div>
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-[#c4b5fd]">{block.title || '商品'}</div>
        {block.description && (
          <p className="mt-1 line-clamp-2 text-xs text-[var(--text-muted)]">{block.description}</p>
        )}
        {block.url && (
          <a href={block.url} target="_blank" rel="noopener noreferrer" className="mt-1.5 inline-block text-xs text-[#7dd3fc] hover:underline">
            查看商品链接 →
          </a>
        )}
      </div>
    </div>
  )
}

function QuickActions({ block }) {
  return (
    <div className="flex flex-wrap gap-2">
      {(block.actions || []).map((action, index) => (
        <button
          key={index}
          type="button"
          onClick={() => {
            const input = document.querySelector('[data-smart-input] textarea, [data-smart-input] input')
            if (input) {
              input.value = action.hint || action.label
              input.dispatchEvent(new Event('input', { bubbles: true }))
              input.focus()
            }
          }}
          className="rounded-full border border-[#38bdf8]/30 bg-[#38bdf8]/10 px-4 py-2 text-sm text-[#7dd3fc] transition-colors hover:border-[#38bdf8]/50 hover:bg-[#38bdf8]/20"
        >
          {action.label}
        </button>
      ))}
    </div>
  )
}

function FrameEditor({ block }) {
  const fieldLabels = {
    description: '画面描述',
    narration: '旁白',
    image_prompt: '图片提示词',
    video_prompt: '视频提示词',
    duration: '时长(秒)',
  }

  return (
    <div className="rounded-xl border border-[#a78bfa]/25 bg-[#1a0f2e]/50 p-4">
      <div className="mb-3 text-sm font-semibold text-[#c4b5fd]">分镜 #{block.sequence} 预览</div>
      <div className="space-y-3">
        {Object.entries(block.fields || {}).map(([key, field]) =>
          field.editable ? (
            <div key={key}>
              <label className="mb-1 block text-xs text-[var(--text-muted)]">{fieldLabels[key] || key}</label>
              <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white">
                {(key === 'duration' ? formatDurationLabel(field.value) : String(field.value ?? '')) || '无'}
              </div>
            </div>
          ) : null
        )}
      </div>
      <div className="mt-4 rounded-lg border border-[#a78bfa]/20 bg-[#a78bfa]/10 px-3 py-2 text-xs leading-6 text-[#ddd6fe]">
        这个版本你想怎么调？
        你可以直接回复比如“分镜 {block.sequence} 换成男生主角”、“旁白更口语一点”，
        “这张图重来，构图更自然一些”，我会继续按你的意思改。
      </div>
    </div>
  )
}

function ConfirmationPreview({ block }) {
  return (
    <div className="rounded-xl border border-[#f59e0b]/25 bg-[#3b2505]/35 p-4">
      <div className="text-sm text-[#fbbf24]">{block.message}</div>
      {block.target_frames?.length > 0 ? (
        <div className="mt-2 text-xs text-[var(--text-muted)]">
          影响分镜: {block.target_frames.map((frame) => `#${frame}`).join(', ')}
        </div>
      ) : null}
      <div className="mt-3 rounded-lg border border-[#f59e0b]/20 bg-[#f59e0b]/10 px-3 py-2 text-xs leading-6 text-[#fde68a]">
        方向还有没有要调的？
        如果这个方案可以，直接回复“继续”或“好的”。
        如果还想改，也可以直接告诉我具体想调整哪一镜、卖点、节奏，或者画面感觉。
      </div>
    </div>
  )
}
