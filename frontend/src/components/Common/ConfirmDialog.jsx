import { useEffect } from 'react'

/**
 * 通用确认对话框
 * @param open - 是否显示
 * @param title - 标题
 * @param message - 提示内容
 * @param onConfirm - 确认回调
 * @param onCancel - 取消回调
 */
export default function ConfirmDialog({ open, title, message, onConfirm, onCancel }) {
  useEffect(() => {
    if (!open) return
    const handleKey = (e) => {
      if (e.key === 'Escape') onCancel?.()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="w-[400px] max-w-[90vw] rounded-xl border border-[var(--border-soft)] bg-[rgba(26,26,46,0.95)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="m-0 mb-3 text-base font-semibold text-white">{title}</h3>
        <p className="m-0 mb-6 text-sm leading-6 text-[var(--text-muted)]">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            className="rounded-lg border border-[var(--border-soft)] bg-transparent px-4 py-2 text-sm text-[var(--text-muted)] transition hover:bg-[rgba(255,255,255,0.05)]"
            onClick={onCancel}
          >
            取消
          </button>
          <button
            type="button"
            className="rounded-lg border border-red-500/30 bg-red-500/20 px-4 py-2 text-sm text-red-400 transition hover:bg-red-500/30"
            onClick={onConfirm}
          >
            删除
          </button>
        </div>
      </div>
    </div>
  )
}
