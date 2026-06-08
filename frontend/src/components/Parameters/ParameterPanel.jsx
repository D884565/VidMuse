import { useAppStore } from '../../store/appStore.js'
import { formatVideoStyle } from '../../utils/videoStyle.js'

const styles = ['product', 'cinematic', 'anime', 'realistic']

const VOICE_OPTIONS = [
  { value: 'zh_female_cancan_mars_bigtts', label: '温柔女声' },
  { value: 'zh_male_kailangxuezhang_uranus_bigtts', label: '清爽男声' },
]

export default function ParameterPanel() {
  const parameters = useAppStore((state) => state.parameters)
  const updateParameters = useAppStore((state) => state.updateParameters)

  return (
    <div className="absolute bottom-full right-0 mb-3 w-[520px] rounded-xl border border-[rgba(124,58,237,0.2)] bg-[rgba(26,26,46,0.95)] p-5 shadow-[0_4px_24px_rgba(124,58,237,0.15)] backdrop-blur-xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="m-0 text-base font-semibold">生成参数</h2>
        <span className="text-xs text-[var(--text-muted)]">应用到当前对话</span>
      </div>

      {/* 风格 */}
      <div>
        <p className="mb-3 text-xs text-[var(--text-muted)]">风格</p>
        <div className="flex flex-wrap gap-2">
          {styles.map((style) => (
            <button
              key={style}
              className={`rounded-lg border px-3 py-2 text-sm ${
                parameters.style === style
                  ? 'border-[#7c3aed] bg-[rgba(124,58,237,0.18)] text-white shadow-[0_0_18px_rgba(124,58,237,0.22)]'
                  : 'border-[var(--border-soft)] text-[var(--text-muted)] hover:border-[rgba(124,58,237,0.45)] hover:text-white'
              }`}
              type="button"
              onClick={() => updateParameters({ style })}
            >
              {formatVideoStyle(style)}
            </button>
          ))}
        </div>
      </div>

      {/* 音色 */}
      <div className="mt-5">
        <p className="mb-3 text-xs text-[var(--text-muted)]">音色</p>
        <div className="flex flex-wrap gap-2">
          {VOICE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`rounded-lg border px-3 py-2 text-sm ${
                parameters.voice_type === opt.value
                  ? 'border-[#7c3aed] bg-[rgba(124,58,237,0.18)] text-white shadow-[0_0_18px_rgba(124,58,237,0.22)]'
                  : 'border-[var(--border-soft)] text-[var(--text-muted)] hover:border-[rgba(124,58,237,0.45)] hover:text-white'
              }`}
              type="button"
              onClick={() => updateParameters({ voice_type: opt.value })}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
