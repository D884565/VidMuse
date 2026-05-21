import { Check, X } from 'lucide-react'

function formatSize(size) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

export default function FilePreview({ file, onRemove }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-[var(--border-soft)] bg-[rgba(26,26,46,0.92)] px-3 py-2 text-xs">
      <Check size={14} className="text-[var(--success)]" />
      <span className="max-w-[180px] truncate text-white">{file.name}</span>
      <span className="text-[var(--text-muted)]">{formatSize(file.size)}</span>
      <button
        className="rounded p-1 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.08)] hover:text-white"
        type="button"
        onClick={() => onRemove(file.id)}
        aria-label="移除文件"
      >
        <X size={14} />
      </button>
    </div>
  )
}
