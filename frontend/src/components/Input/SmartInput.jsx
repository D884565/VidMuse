import { Image, Send, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import ParameterPanel from '../Parameters/ParameterPanel.jsx'

export default function SmartInput({ onSend }) {
  const [value, setValue] = useState('')
  const [panelOpen, setPanelOpen] = useState(false)
  const canSend = value.trim().length > 0

  function submit(event) {
    event.preventDefault()
    if (!canSend) return
    onSend(value)
    setValue('')
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      submit(event)
    }
  }

  return (
    <div className="fixed bottom-0 left-[260px] right-0 z-20 border-t border-[var(--border-soft)] bg-[rgba(15,15,26,0.88)] px-8 py-5 backdrop-blur-xl transition-[left] duration-300 max-[1024px]:left-[72px]">
      <div className="relative mx-auto max-w-4xl">
        {panelOpen && <ParameterPanel />}

        <form
          className="rounded-xl border border-[rgba(124,58,237,0.22)] bg-[rgba(26,26,46,0.95)] p-3 shadow-[0_4px_24px_rgba(124,58,237,0.15)]"
          onSubmit={submit}
        >
          <textarea
            className="max-h-[200px] min-h-12 w-full resize-none bg-transparent px-2 py-1 text-sm leading-6 text-white outline-none placeholder:text-[var(--text-muted)]"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="鎻忚堪浣犳兂鐢熸垚鐨勮棰戯紝Shift + Enter 鎹㈣"
          />

          <div className="mt-2 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white"
                type="button"
                aria-label="素材库"
              >
                <Image size={18} />
              </button>
              <button
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--brand-soft)] hover:text-white"
                type="button"
                onClick={() => setPanelOpen((open) => !open)}
              >
                <SlidersHorizontal size={18} />
                参数
              </button>
            </div>

            <button
              className={`grid h-10 w-10 place-items-center rounded-lg ${
                canSend
                  ? 'bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] text-white shadow-[0_4px_24px_rgba(124,58,237,0.25)]'
                  : 'cursor-not-allowed bg-[rgba(148,163,184,0.12)] text-[rgba(148,163,184,0.5)]'
              }`}
              type="submit"
              disabled={!canSend}
              aria-label="Send message"
            >
              <Send size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
