import { Upload } from 'lucide-react'
import MediaCard from './MediaCard.jsx'

const mediaItems = [
  { id: 'm1', name: 'product-shot.mp4', meta: '12s · MP4', type: 'video' },
  { id: 'm2', name: 'logo-clean.png', meta: '1.2 MB · PNG', type: 'image' },
  { id: 'm3', name: 'voice-over.wav', meta: '18s · WAV', type: 'audio' },
  { id: 'm4', name: 'hero-scene.jpg', meta: '2.4 MB · JPG', type: 'image' },
]

export default function MediaGrid() {
  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6">
        <h1 className="m-0 text-lg font-semibold">素材库</h1>
        <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
          管理视频、图片、音频素材，并在对话生成时快速引用。
        </p>
      </header>

      <div className="mb-6 grid min-h-36 place-items-center rounded-xl border border-dashed border-[rgba(124,58,237,0.35)] bg-[rgba(26,26,46,0.65)] text-center hover:bg-[rgba(124,58,237,0.1)]">
        <div>
          <Upload className="mx-auto mb-3 text-[#a78bfa]" size={24} />
          <p className="m-0 text-sm font-medium">拖拽文件到此处开始上传</p>
          <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">支持视频、图片、音频格式</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 max-[1280px]:grid-cols-3">
        {mediaItems.map((item) => (
          <MediaCard key={item.id} item={item} />
        ))}
      </div>
    </section>
  )
}
