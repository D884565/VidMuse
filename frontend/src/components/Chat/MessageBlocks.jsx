import { Play, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { advanceWorkflowStage, confirmWorkflowStage } from '../../services/project.js'
import { useAppStore } from '../../store/appStore.js'

/**
 * 消息结构化块渲染器
 * 根据后端返回的 blocks 数组，渲染对应的 UI 组件（剧本摘要、分镜表格、图片网格等）。
 */
export default function MessageBlocks({ blocks = [], onActionComplete }) {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const [pendingActionKey, setPendingActionKey] = useState('')
  const [actionError, setActionError] = useState('')

  /** 执行操作按钮的动作：确认阶段 或 确认并推进到下一阶段 */
  async function runAction(action) {
    if (!activeProjectId || pendingActionKey) return
    const actionKey = `${action.action}-${action.stage || action.confirmed_stage || action.label}`
    setPendingActionKey(actionKey)
    setActionError('')
    try {
      if (action.action === 'confirm') {
        await confirmWorkflowStage(activeProjectId, action.stage)
      } else if (action.action === 'advance') {
        await advanceWorkflowStage(activeProjectId, action.confirmed_stage)
      }
      onActionComplete?.()
    } catch (err) {
      // 操作失败时留在当前消息块内提示，避免未处理 Promise 异常。
      setActionError(err.message || '操作失败')
    } finally {
      setPendingActionKey('')
    }
  }

  if (!blocks?.length) return null

  return (
    <div className="mt-4 space-y-4">
      {blocks.map((block, index) => {
        if (block.type === 'script_summary') return <ScriptSummary key={index} block={block} />
        if (block.type === 'storyboard_table') return <StoryboardTable key={index} block={block} />
        if (block.type === 'image_grid') return <ImageGrid key={index} block={block} />
        if (block.type === 'video_card') return <VideoCard key={index} block={block} />
        if (block.type === 'progress_card') return <ProgressCard key={index} block={block} />
        if (block.type === 'action_bar') {
          return (
            <ActionBar
              key={index}
              block={block}
              onRun={runAction}
              pendingActionKey={pendingActionKey}
              actionError={actionError}
            />
          )
        }
        if (block.type === 'asset_grid') return <AssetGrid key={index} block={block} />
        return null
      })}
    </div>
  )
}

/** 剧本方案摘要卡片：显示主题、风格、分镜数、总时长 */
function ScriptSummary({ block }) {
  return (
    <div className="rounded-xl border border-[#38bdf8]/25 bg-[#0f2a3a]/45 p-4">
      <div className="text-sm font-semibold text-[#7dd3fc]">{block.title || '剧本方案'}</div>
      <div className="mt-2 grid gap-2 text-xs text-slate-200 sm:grid-cols-2">
        <p className="m-0">主题：{block.theme}</p>
        <p className="m-0">风格：{block.style}</p>
        <p className="m-0">分镜数：{block.frame_count}</p>
        <p className="m-0">总时长：{block.total_duration}s</p>
      </div>
      <p className="mb-0 mt-3 text-xs text-[var(--text-muted)]">{block.visual_plan}</p>
    </div>
  )
}

/** 分镜表格：展示每个分镜的序号、时长、画面描述和旁白 */
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
          <span>{frame.duration}s</span>
          <div>
            <p className="m-0 text-white">{frame.scene}</p>
            <p className="mb-0 mt-1 text-[var(--text-muted)]">{frame.narration}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

/** 图片网格：展示每个分镜的首帧图片 */
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

/** 视频播放卡片：展示最终成片视频 */
function VideoCard({ block }) {
  return (
    <div className="rounded-xl border border-[#10b981]/25 bg-[#052e24]/50 p-4">
      <div className="mb-3 flex items-center gap-2 font-semibold text-[#6ee7b7]">
        <Play size={16} />
        视频成片
      </div>
      {block.video_url ? (
        <video src={block.video_url} controls className="w-full rounded-lg bg-black" />
      ) : (
        <div className="rounded-lg bg-black/40 p-6 text-center text-sm text-[var(--text-muted)]">视频生成中</div>
      )}
    </div>
  )
}

/** 进度卡片：显示当前任务的阶段和状态 */
function ProgressCard({ block }) {
  return (
    <div className="rounded-xl border border-[#f59e0b]/25 bg-[#3b2505]/35 p-4 text-sm">
      <div className="flex items-center gap-2 text-[#fbbf24]">
        <RefreshCw size={15} />
        {block.message}
      </div>
      <div className="mt-2 text-xs text-[var(--text-muted)]">阶段：{block.stage} · 状态：{block.status}</div>
    </div>
  )
}

/** 操作按钮栏：渲染确认、推进、重新生成等操作按钮 */
function ActionBar({ block, onRun, pendingActionKey, actionError }) {
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {(block.actions || []).map((action, index) => {
          const actionKey = `${action.action}-${action.stage || action.confirmed_stage || action.label}`
          const busy = pendingActionKey === actionKey
          return (
            <button
              key={`${action.label}-${index}`}
              type="button"
              disabled={!!pendingActionKey}
              onClick={() => onRun(action)}
              className="rounded-full border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs text-white hover:border-[#38bdf8]/40 hover:bg-[#38bdf8]/10 disabled:cursor-wait disabled:opacity-50"
            >
              {busy ? '处理中...' : action.label}
            </button>
          )
        })}
      </div>
      {actionError && <div className="mt-2 text-xs text-red-300">{actionError}</div>}
    </div>
  )
}

/** 素材网格：展示参考图、商品图等素材 */
function AssetGrid({ block }) {
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {(block.assets || []).map((asset, index) => (
        <div key={asset.url || index} className="rounded-lg border border-white/10 p-2 text-xs text-[var(--text-muted)]">
          {asset.url || asset.title || '素材'}
        </div>
      ))}
    </div>
  )
}
