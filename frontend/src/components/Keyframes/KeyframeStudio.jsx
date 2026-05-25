import { AlertCircle, Film, Image, LoaderCircle, SlidersHorizontal, Upload } from 'lucide-react'
import { useMemo, useState } from 'react'

const initialSettings = {
  changeThreshold: 8,
  minIntervalSeconds: 0.5,
  resizeWidth: 320,
  maxKeyframes: 20,
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-3">
      <p className="m-0 text-xs text-[var(--text-muted)]">{label}</p>
      <p className="m-0 mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  )
}

export default function KeyframeStudio() {
  const [file, setFile] = useState(null)
  const [settings, setSettings] = useState(initialSettings)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const fileMeta = useMemo(() => {
    if (!file) return ''
    const sizeMb = file.size / 1024 / 1024
    return `${file.name} - ${sizeMb.toFixed(2)} MB`
  }, [file])

  const updateSetting = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }))
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!file) {
      setError('Please select a video file.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    const body = new FormData()
    body.append('file', file)
    body.append('change_threshold', String(settings.changeThreshold))
    body.append('min_interval_seconds', String(settings.minIntervalSeconds))
    body.append('resize_width', String(settings.resizeWidth))
    body.append('max_keyframes', String(settings.maxKeyframes))

    try {
      const response = await fetch('/opencv-api/video/keyframes/change-detect', {
        method: 'POST',
        body,
      })

      if (!response.ok) {
        throw new Error(await response.text())
      }

      setResult(await response.json())
    } catch (requestError) {
      setError(requestError.message || 'Keyframe extraction failed.')
    } finally {
      setLoading(false)
    }
  }

  const keyframes = result?.keyframes ?? []

  return (
    <section className="min-h-screen px-8 py-8">
      <header className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="m-0 text-lg font-semibold">Keyframe Extraction</h1>
          <p className="m-0 mt-1 text-sm text-[var(--text-muted)]">
            {result ? result.message : 'Upload a video and extract scene-change keyframes.'}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-[rgba(16,185,129,0.28)] bg-[rgba(16,185,129,0.08)] px-3 py-2 text-xs text-emerald-200">
          <Film size={16} />
          OpenCV
        </div>
      </header>

      <form
        className="mb-6 grid gap-4 rounded-lg border border-[var(--border-soft)] bg-[rgba(19,19,31,0.88)] p-5"
        onSubmit={submit}
      >
        <label className="grid min-h-36 cursor-pointer place-items-center rounded-lg border border-dashed border-[rgba(56,189,248,0.36)] bg-[rgba(14,116,144,0.08)] px-4 text-center hover:bg-[rgba(14,116,144,0.14)]">
          <input
            className="sr-only"
            type="file"
            accept="video/*"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <span>
            <Upload className="mx-auto mb-3 text-sky-300" size={26} />
            <span className="block text-sm font-medium text-white">
              {file ? fileMeta : 'Choose a video file'}
            </span>
          </span>
        </label>

        <div className="grid grid-cols-4 gap-3 max-[1180px]:grid-cols-2 max-[760px]:grid-cols-1">
          <label className="grid gap-2 text-xs text-[var(--text-muted)]">
            <span>Change threshold</span>
            <input
              className="h-10 rounded-lg border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-3 text-sm text-white outline-none focus:border-sky-400"
              min="0"
              step="0.5"
              type="number"
              value={settings.changeThreshold}
              onChange={(event) => updateSetting('changeThreshold', event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-xs text-[var(--text-muted)]">
            <span>Minimum interval</span>
            <input
              className="h-10 rounded-lg border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-3 text-sm text-white outline-none focus:border-sky-400"
              min="0"
              step="0.1"
              type="number"
              value={settings.minIntervalSeconds}
              onChange={(event) => updateSetting('minIntervalSeconds', event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-xs text-[var(--text-muted)]">
            <span>Detection width</span>
            <input
              className="h-10 rounded-lg border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-3 text-sm text-white outline-none focus:border-sky-400"
              max="1920"
              min="32"
              type="number"
              value={settings.resizeWidth}
              onChange={(event) => updateSetting('resizeWidth', event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-xs text-[var(--text-muted)]">
            <span>Max keyframes</span>
            <input
              className="h-10 rounded-lg border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-3 text-sm text-white outline-none focus:border-sky-400"
              max="500"
              min="1"
              type="number"
              value={settings.maxKeyframes}
              onChange={(event) => updateSetting('maxKeyframes', event.target.value)}
            />
          </label>
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <SlidersHorizontal size={16} />
            <span>threshold {settings.changeThreshold}</span>
          </div>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-sky-500 px-4 text-sm font-semibold text-white hover:bg-sky-400 disabled:cursor-wait disabled:bg-sky-900"
            disabled={loading}
            type="submit"
          >
            {loading ? <LoaderCircle className="animate-spin" size={17} /> : <Image size={17} />}
            {loading ? 'Processing' : 'Extract keyframes'}
          </button>
        </div>
      </form>

      {error && (
        <div className="mb-6 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          <AlertCircle className="mt-0.5 shrink-0" size={17} />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="mb-6 grid grid-cols-6 gap-3 max-[1280px]:grid-cols-3 max-[760px]:grid-cols-2">
          <Stat label="Saved" value={result.saved_count} />
          <Stat label="Frames" value={result.frame_count} />
          <Stat label="FPS" value={result.fps} />
          <Stat label="Size" value={`${result.width}x${result.height}`} />
          <Stat label="Threshold" value={result.change_threshold} />
          <Stat label="Interval" value={`${result.min_interval_seconds}s`} />
        </div>
      )}

      <div className="grid grid-cols-4 gap-3 max-[1320px]:grid-cols-3 max-[980px]:grid-cols-2 max-[640px]:grid-cols-1">
        {keyframes.map((frame) => (
          <article
            className="overflow-hidden rounded-lg border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)]"
            key={`${frame.frame_index}-${frame.change_score}`}
          >
            <img
              alt={`Frame ${frame.frame_index}`}
              className="aspect-video w-full object-cover"
              src={`/opencv-api${frame.url}?t=${Date.now()}`}
            />
            <div className="grid gap-1 px-3 py-3 text-xs text-[var(--text-muted)]">
              <strong className="text-sm text-white">Frame {frame.frame_index}</strong>
              <span>{frame.timestamp_seconds}s</span>
              <span>score {frame.change_score}</span>
            </div>
          </article>
        ))}
      </div>

      {result && keyframes.length === 0 && (
        <div className="rounded-lg border border-[var(--border-soft)] bg-[rgba(255,255,255,0.04)] px-4 py-8 text-center text-sm text-[var(--text-muted)]">
          No keyframes were saved. Try lowering the change threshold.
        </div>
      )}
    </section>
  )
}
