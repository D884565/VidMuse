const ratios = [
  { value: '16:9', label: '横屏' },
  { value: '9:16', label: '竖屏' },
  { value: '1:1', label: '方形' },
  { value: '4:3', label: '经典' },
]

export default function AspectRatioSelector({ value, onChange }) {
  return (
    <div>
      <p className="mb-3 text-xs text-[var(--text-muted)]">视频比例</p>
      <div className="grid grid-cols-4 gap-2">
        {ratios.map((ratio) => (
          <button
            key={ratio.value}
            className={`rounded-xl border p-3 text-left ${
              value === ratio.value
                ? 'border-[#7c3aed] bg-[rgba(124,58,237,0.18)] shadow-[0_0_18px_rgba(124,58,237,0.22)]'
                : 'border-[var(--border-soft)] hover:border-[rgba(124,58,237,0.45)]'
            }`}
            type="button"
            onClick={() => onChange(ratio.value)}
          >
            <div className="mb-2 h-8 rounded border border-[rgba(148,163,184,0.22)] bg-[rgba(255,255,255,0.04)]" />
            <p className="m-0 text-sm font-medium">{ratio.value}</p>
            <p className="m-0 text-xs text-[var(--text-muted)]">{ratio.label}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
