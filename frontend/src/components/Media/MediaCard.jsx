import { Image, Music, Play, Trash2 } from 'lucide-react'

const iconMap = {
  video: Play,
  image: Image,
  audio: Music,
}

export default function MediaCard({ item }) {
  const Icon = iconMap[item.type] || Image

  return (
    <article className="group overflow-hidden rounded-xl border border-[var(--border-soft)] bg-[rgba(26,26,46,0.72)] transition hover:-translate-y-0.5 hover:border-[rgba(124,58,237,0.45)] hover:shadow-[0_4px_24px_rgba(124,58,237,0.15)]">
      <div className="grid aspect-video place-items-center bg-[rgba(255,255,255,0.04)]">
        <Icon size={28} className="text-[#a78bfa]" />
      </div>
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="m-0 truncate text-sm font-medium">{item.name}</p>
            <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">{item.meta}</p>
          </div>
          <button
            className="rounded-lg p-2 text-[var(--text-muted)] opacity-0 hover:bg-[rgba(255,255,255,0.08)] hover:text-white group-hover:opacity-100"
            type="button"
            aria-label="删除素材"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>
    </article>
  )
}
