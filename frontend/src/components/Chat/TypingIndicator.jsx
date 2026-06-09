/** 正在输入指示器 — 三个跳动的圆点，表示 AI 正在生成回复 */
export default function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1 rounded-xl border-l-[3px] border-[#7c3aed] bg-[rgba(26,26,46,0.86)] px-4 py-3">
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="h-2 w-2 rounded-full bg-[#a855f7]"
            style={{ animation: `pulse-dot 900ms ${dot * 120}ms infinite` }}
          />
        ))}
      </div>
    </div>
  )
}
