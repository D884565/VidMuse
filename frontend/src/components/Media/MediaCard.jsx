import { FileText, Image, Music, Play, Trash2 } from 'lucide-react'

const iconMap = {
  video: Play,
  image: Image,
  audio: Music,
  text: FileText,
}

export default function MediaCard({ item, onClick, onDelete }) {
  const Icon = iconMap[item.type] || Image

  const handleDelete = (e) => {
    e.stopPropagation()
    onDelete?.(item.id)
  }

  const renderPreview = () => {
    if (item.type === 'image' && item.url) {
      return <img src={item.url} alt={item.name} className="h-full w-full object-contain p-2" />
    }
    return <Icon size={28} className="text-[#a78bfa]" />
  }

  return (
    <button
      type="button"
      onClick={() => onClick?.(item)}
      className="group w-full overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[rgba(26,26,46,0.72)] text-left transition hover:-translate-y-0.5 hover:border-[rgba(124,58,237,0.45)] hover:shadow-[0_4px_24px_rgba(124,58,237,0.15)]"
    >
      <div className="relative grid aspect-video place-items-center overflow-hidden bg-[rgba(255,255,255,0.04)]">
        {renderPreview()}
        {/* Delete button on hover */}
        <div className="absolute right-2 top-2 opacity-0 transition group-hover:opacity-100">
          <span
            role="button"
            tabIndex={0}
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/15 bg-[rgba(15,23,42,0.86)] text-white transition hover:bg-red-500/80"
            aria-label="删除素材"
            onClick={handleDelete}
            onKeyDown={(e) => e.key === 'Enter' && handleDelete(e)}
          >
            <Trash2 size={14} />
          </span>
        </div>
      </div>
      <div className="p-3">
        <p className="m-0 truncate text-sm font-medium text-white">{item.name}</p>
        <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">{item.meta}</p>
        {item.type === 'text' && item.content_text && (
          <p className="m-0 mt-2 line-clamp-2 text-xs leading-4 text-[var(--text-muted)]">
            {item.content_text}
          </p>
        )}
      </div>
    </button>
  )
}
