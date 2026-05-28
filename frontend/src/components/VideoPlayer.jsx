import { useRef, useState } from 'react'
import { Play, Pause, Volume2, VolumeX } from 'lucide-react'

export default function VideoPlayer({ src }) {
  const videoRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [muted, setMuted] = useState(false)

  if (!src) {
    return (
      <div className="flex items-center justify-center h-48 rounded-xl border border-dashed border-[var(--border-soft)] bg-[var(--bg-secondary)]">
        <p className="text-sm text-[var(--text-muted)]">暂无视频</p>
      </div>
    )
  }

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) {
      video.play()
      setPlaying(true)
    } else {
      video.pause()
      setPlaying(false)
    }
  }

  const handleTimeUpdate = () => {
    const video = videoRef.current
    if (!video || !video.duration) return
    setProgress((video.currentTime / video.duration) * 100)
  }

  const handleSeek = (e) => {
    const video = videoRef.current
    if (!video || !video.duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    video.currentTime = ratio * video.duration
  }

  const toggleMute = () => {
    const video = videoRef.current
    if (!video) return
    video.muted = !video.muted
    setMuted(video.muted)
  }

  return (
    <div className="relative rounded-xl overflow-hidden bg-black group">
      <video
        ref={videoRef}
        src={src}
        className="w-full max-h-[480px] object-contain"
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setPlaying(false)}
        onClick={togglePlay}
      />

      {/* 控制栏 */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-3 opacity-0 group-hover:opacity-100 transition-opacity">
        {/* 进度条 */}
        <div
          className="w-full h-1 bg-white/20 rounded-full mb-2 cursor-pointer"
          onClick={handleSeek}
        >
          <div
            className="h-full bg-[#7C3AED] rounded-full transition-[width] duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="flex items-center gap-3">
          <button onClick={togglePlay} className="text-white hover:text-[#c4b5fd] transition-colors">
            {playing ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button onClick={toggleMute} className="text-white hover:text-[#c4b5fd] transition-colors">
            {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
        </div>
      </div>

      {/* 中心播放按钮（暂停时显示） */}
      {!playing && (
        <div
          className="absolute inset-0 flex items-center justify-center cursor-pointer"
          onClick={togglePlay}
        >
          <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <Play size={24} className="text-white ml-1" />
          </div>
        </div>
      )}
    </div>
  )
}
