import { useState, useEffect, useRef } from 'react'
import { Loader2, XCircle, CheckCircle2, AlertCircle } from 'lucide-react'
import { replaceAudio, addBgm, getMergeTaskStatus, cancelMergeTask } from '../../services/merge.js'

const STATUS_DISPLAY = {
  queued: { text: '排队中', color: 'text-yellow-400', icon: Loader2 },
  processing: { text: '处理中', color: 'text-blue-400', icon: Loader2 },
  completed: { text: '已完成', color: 'text-green-400', icon: CheckCircle2 },
  failed: { text: '失败', color: 'text-red-400', icon: AlertCircle },
  cancelled: { text: '已取消', color: 'text-gray-400', icon: XCircle },
}

export default function MergePanel({ videoId, assets = [] }) {
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const intervalRef = useRef(null)

  // 可用的音频素材
  const audioAssets = assets.filter((a) => a.type === 3)

  // 轮询任务状态
  useEffect(() => {
    if (!task || task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
      return
    }

    intervalRef.current = setInterval(async () => {
      try {
        const data = await getMergeTaskStatus(task.task_id)
        setTask((prev) => ({ ...prev, ...data }))
        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
          clearInterval(intervalRef.current)
        }
      } catch (err) {
        console.warn('查询任务状态失败:', err.message)
      }
    }, 3000)

    return () => clearInterval(intervalRef.current)
  }, [task?.task_id, task?.status])

  const handleReplaceAudio = async (audioId) => {
    if (!videoId || !audioId) return
    setLoading(true)
    setError('')
    try {
      const data = await replaceAudio(videoId, audioId)
      setTask(data)
    } catch (err) {
      setError(err.message || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAddBgm = async (bgmId) => {
    if (!videoId || !bgmId) return
    setLoading(true)
    setError('')
    try {
      const data = await addBgm(videoId, bgmId, 0.3, 1.0)
      setTask(data)
    } catch (err) {
      setError(err.message || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!task?.task_id) return
    try {
      await cancelMergeTask(task.task_id)
      setTask((prev) => ({ ...prev, status: 'cancelled' }))
    } catch (err) {
      setError(err.message || '取消失败')
    }
  }

  const statusInfo = task ? STATUS_DISPLAY[task.status] : null
  const StatusIcon = statusInfo?.icon

  return (
    <div className="rounded-xl border border-[var(--border-soft)] bg-[var(--bg-secondary)] p-4">
      <h3 className="text-sm font-medium mb-3">音视频合成</h3>

      {error && (
        <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* 操作按钮 */}
      {!task && (
        <div className="space-y-3">
          {audioAssets.length > 0 ? (
            <>
              <div>
                <p className="text-xs text-[var(--text-muted)] mb-2">替换音频</p>
                <div className="flex flex-wrap gap-2">
                  {audioAssets.map((audio) => (
                    <button
                      key={audio.id}
                      onClick={() => handleReplaceAudio(audio.id)}
                      disabled={loading}
                      className="px-3 py-1.5 text-xs rounded-lg border border-[var(--border-soft)] text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50 transition-colors"
                    >
                      {loading ? '...' : (audio.title || `音频 ${audio.id}`)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-[var(--text-muted)] mb-2">添加背景音乐</p>
                <div className="flex flex-wrap gap-2">
                  {audioAssets.map((audio) => (
                    <button
                      key={`bgm-${audio.id}`}
                      onClick={() => handleAddBgm(audio.id)}
                      disabled={loading}
                      className="px-3 py-1.5 text-xs rounded-lg border border-[var(--border-soft)] text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white disabled:opacity-50 transition-colors"
                    >
                      {loading ? '...' : (audio.title || `BGM ${audio.id}`)}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">暂无可用音频素材，请先在素材库中上传。</p>
          )}
        </div>
      )}

      {/* 任务状态 */}
      {task && statusInfo && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <StatusIcon
              size={16}
              className={`${statusInfo.color} ${['queued', 'processing'].includes(task.status) ? 'animate-spin' : ''}`}
            />
            <span className={`text-sm ${statusInfo.color}`}>{statusInfo.text}</span>
            <span className="text-xs text-[var(--text-muted)]">任务 {task.task_id}</span>
          </div>
          {task.error_message && (
            <p className="text-xs text-red-400">{task.error_message}</p>
          )}
          {task.result?.output_path && (
            <p className="text-xs text-green-400">输出: {task.result.output_path}</p>
          )}
          {['queued', 'processing'].includes(task.status) && (
            <button
              onClick={handleCancel}
              className="px-3 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
            >
              取消任务
            </button>
          )}
          {['completed', 'failed', 'cancelled'].includes(task.status) && (
            <button
              onClick={() => setTask(null)}
              className="px-3 py-1.5 text-xs rounded-lg border border-[var(--border-soft)] text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white transition-colors"
            >
              新建任务
            </button>
          )}
        </div>
      )}
    </div>
  )
}
