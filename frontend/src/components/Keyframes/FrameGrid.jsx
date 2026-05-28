import { useState } from 'react'
import { RefreshCw, Image, Loader2 } from 'lucide-react'
import { useProjectPolling } from '../../hooks/useProjectPolling.js'
import { useAppStore } from '../../store/appStore.js'
import { regenerateFrame, regenerateFrameImage } from '../../services/frame.js'
import MergePanel from '../Merge/MergePanel.jsx'
import VideoPlayer from '../VideoPlayer.jsx'

// 帧状态映射
const STATUS_MAP = {
  0: { text: '待生成', color: 'text-yellow-400' },
  1: { text: '剧本就绪', color: 'text-purple-400' },
  2: { text: '生成中', color: 'text-blue-400' },
  3: { text: '已完成', color: 'text-green-400' },
  4: { text: '失败', color: 'text-red-400' },
}

// 场景类型映射
const SCENE_TYPE_MAP = {
  0: '开场',
  1: '商品展示',
  2: '口播',
  3: '转场',
  4: '结尾',
}

export default function FrameGrid() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const { frames, videoUrl, videoAssetId, assets, loading, error } = useProjectPolling(activeProjectId)
  const [regenerating, setRegenerating] = useState({}) // { [frameId]: 'script' | 'image' }

  // 重新生成脚本+图片
  const handleRegenerate = async (frameId) => {
    const instruction = prompt('请输入调整指令（可选）')
    if (instruction === null) return // 用户取消
    setRegenerating((prev) => ({ ...prev, [frameId]: 'script' }))
    try {
      await regenerateFrame(activeProjectId, frameId, instruction || undefined)
      // 轮询会自动刷新帧数据
    } catch (err) {
      alert(`重新生成失败: ${err.message}`)
    } finally {
      setRegenerating((prev) => {
        const next = { ...prev }
        delete next[frameId]
        return next
      })
    }
  }

  // 仅重新生成图片
  const handleRegenerateImage = async (frameId) => {
    const instruction = prompt('请输入图片调整指令（可选）')
    if (instruction === null) return
    setRegenerating((prev) => ({ ...prev, [frameId]: 'image' }))
    try {
      await regenerateFrameImage(activeProjectId, frameId, instruction || undefined)
    } catch (err) {
      alert(`重新生成图片失败: ${err.message}`)
    } finally {
      setRegenerating((prev) => {
        const next = { ...prev }
        delete next[frameId]
        return next
      })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="animate-spin text-[#7C3AED]" size={32} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen text-red-400">
        {error}
      </div>
    )
  }

  if (!frames.length) {
    return (
      <div className="flex items-center justify-center min-h-screen text-[var(--text-muted)]">
        暂无帧数据
      </div>
    )
  }

  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6">
        <h1 className="m-0 text-lg font-semibold">关键帧管理</h1>
        <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
          查看和重新生成视频帧
        </p>
      </header>

      {/* 视频预览 */}
      {videoUrl && (
        <div className="mb-6">
          <VideoPlayer src={videoUrl} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4">
        {frames.map((frame) => {
          const status = STATUS_MAP[frame.status] || STATUS_MAP[0]
          const isRegenerating = regenerating[frame.id]
          return (
            <div
              key={frame.id}
              className="rounded-xl border border-[var(--border-soft)] bg-[var(--bg-secondary)] overflow-hidden"
            >
              {/* 帧图片 */}
              <div className="aspect-video bg-[var(--bg-main)] flex items-center justify-center">
                {frame.image_url ? (
                  <img
                    src={frame.image_url}
                    alt={`帧 ${frame.sequence}`}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <Image size={32} className="text-[var(--text-muted)]" />
                )}
              </div>
              {/* 帧信息 */}
              <div className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">场景 {frame.sequence}</span>
                    {frame.scene_type != null && SCENE_TYPE_MAP[frame.scene_type] && (
                      <span className="rounded-full bg-[rgba(124,58,237,0.2)] px-1.5 py-0.5 text-[10px] text-[#c4b5fd]">
                        {SCENE_TYPE_MAP[frame.scene_type]}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {frame.duration && (
                      <span className="text-xs text-[var(--text-muted)]">{frame.duration}s</span>
                    )}
                    <span className={`text-xs ${status.color}`}>{status.text}</span>
                  </div>
                </div>
                <p className="text-xs text-[var(--text-muted)] line-clamp-2 mb-1">
                  {frame.description || '无描述'}
                </p>
                {frame.text_overlay && (
                  <p className="text-xs text-[#a78bfa] line-clamp-1 mb-1">
                    叠字: {frame.text_overlay}
                  </p>
                )}
                {frame.audio_url && (
                  <div className="mb-2">
                    <audio controls src={frame.audio_url} className="w-full h-7" />
                  </div>
                )}
                {/* 操作按钮 */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleRegenerate(frame.id)}
                    disabled={!!isRegenerating}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs rounded-lg border border-[var(--border-soft)] text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50 transition-colors"
                  >
                    <RefreshCw
                      size={12}
                      className={isRegenerating === 'script' ? 'animate-spin' : ''}
                    />
                    重新生成
                  </button>
                  <button
                    onClick={() => handleRegenerateImage(frame.id)}
                    disabled={!!isRegenerating}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs rounded-lg border border-[var(--border-soft)] text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50 transition-colors"
                  >
                    <Image
                      size={12}
                      className={isRegenerating === 'image' ? 'animate-spin' : ''}
                    />
                    重生成图片
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* 音视频合成面板 */}
      <div className="mt-8">
        <MergePanel videoId={videoAssetId || null} assets={assets} />
      </div>
    </section>
  )
}
