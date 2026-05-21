export default function DurationSlider({ value, onChange }) {
  return (
    <div className="mt-5">
      <div className="mb-3 flex items-center justify-between">
        <p className="m-0 text-xs text-[var(--text-muted)]">视频时长</p>
        <span className="rounded-full bg-[rgba(124,58,237,0.18)] px-2 py-1 text-xs text-[#c4b5fd]">
          {value}s
        </span>
      </div>
      <input
        className="h-2 w-full accent-[#7c3aed]"
        type="range"
        min="5"
        max="120"
        step="5"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className="mt-2 flex justify-between text-[11px] text-[var(--text-muted)]">
        <span>5s</span>
        <span>60s</span>
        <span>120s</span>
      </div>
    </div>
  )
}
