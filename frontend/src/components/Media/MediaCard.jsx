import { FileText, Image, Music, Play, RefreshCw, SquarePen, Trash2 } from 'lucide-react'

const iconMap = {
  video: Play,
  image: Image,
  audio: Music,
  text: FileText,
}

export default function MediaCard({ item, onDelete, onEditText, onReuploadImage }) {
  const Icon = iconMap[item.type] || Image

  const handleDelete = (e) => {
    e.stopPropagation()
    onDelete?.(item.id)
  }

  const handleEdit = (e) => {
    e.stopPropagation()
    onEditText?.(item)
  }

  const handleReupload = (e) => {
    e.stopPropagation()
    onReuploadImage?.(item)
  }

  const renderPreview = () => {
    if (item.type === 'image' && item.url) {
      return <img src={item.url} alt={item.name} className="h-full w-full object-contain p-2" />
    }
    return <Icon size={28} className="text-[#a78bfa]" />
  }

  return (
    <article className="group overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[rgba(26,26,46,0.72)] transition hover:-translate-y-0.5 hover:border-[rgba(124,58,237,0.45)] hover:shadow-[0_4px_24px_rgba(124,58,237,0.15)]">
      <div className="grid aspect-video place-items-center overflow-hidden bg-[rgba(255,255,255,0.04)]">
        {renderPreview()}
      </div>
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="m-0 truncate text-sm font-medium">{item.name}</p>
            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">{item.meta}</p>
          </div>
          <div className="flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
            {item.type === 'text' && (
              <button
                className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.08)] hover:text-white"
                type="button"
                aria-label="编辑文本素材"
                onClick={handleEdit}
              >
                <SquarePen size={15} />
              </button>
            )}
            {item.type === 'image' && (
              <button
                className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.08)] hover:text-white"
                type="button"
                aria-label="重新上传图片素材"
                onClick={handleReupload}
              >
                <RefreshCw size={15} />
              </button>
            )}
            <button
              className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[rgba(255,255,255,0.08)] hover:text-white"
              type="button"
              aria-label="删除素材"
              onClick={handleDelete}
            >
              <Trash2 size={15} />
            </button>
          </div>
        </div>
        {item.type === 'text' && item.content_text && (
          <p className="m-0 mt-3 line-clamp-3 text-xs leading-5 text-[var(--text-muted)]">{item.content_text}</p>
        )}
      </div>
    </article>
  )
}
