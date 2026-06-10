import { useEffect, useRef } from 'react'
import { useProjectEditor } from '../../hooks/useProjectEditor.js'
import { useAppStore } from '../../store/appStore.js'
import SmartInput from '../Input/SmartInput.jsx'
import StageProgress from '../Workflow/StageProgress.jsx'
import MessageBubble from '../Chat/MessageBubble.jsx'
import TypingIndicator from '../Chat/TypingIndicator.jsx'

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content: `我是 VidMuse——带货视频生成 Agent。我会帮你一步步创建带货短视频：

1. 先确认风格、卖点和分镜脚本
2. 再生成每个镜头的首帧图片
3. 最后合成视频并支持继续对话修改

请描述你想推广的产品，或直接粘贴商品链接，我会先给出画面方案。`,
}

export default function WorkbenchView() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const creationMode = useAppStore((state) => state.creationMode)
  const setCreationMode = useAppStore((state) => state.setCreationMode)
  const editor = useProjectEditor()
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const raf = requestAnimationFrame(() => {
      setTimeout(() => {
        el.scrollTop = el.scrollHeight
      }, 50)
    })
    return () => cancelAnimationFrame(raf)
  }, [editor.messages, activeProjectId, editor.isTyping, editor.historyLoaded])

  function handleActionComplete() {
    editor.reloadChat()
    editor.refetch()
  }

  const displayMessages = activeProjectId
    ? editor.messages
    : [WELCOME_MESSAGE, ...editor.messages]

  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0 opacity-70 [background-image:radial-gradient(circle_at_12%_18%,rgba(56,189,248,0.16),transparent_26%),radial-gradient(circle_at_78%_4%,rgba(16,185,129,0.13),transparent_28%),linear-gradient(135deg,rgba(15,23,42,0.4),transparent)]" />

      <header className="relative z-10 border-b border-[var(--border-soft)] px-6 py-5 lg:px-10">
        <div className="mx-auto max-w-6xl">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h1 className="m-0 text-xl font-semibold">对话式视频创作</h1>
              <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
                像聊天一样推进剧本、首帧图片和视频生成
              </p>
            </div>
          </div>
          {activeProjectId && <StageProgress project={editor.project} />}
        </div>
      </header>

      <div ref={scrollRef} className="relative z-10 flex-1 overflow-y-auto px-4 pb-44 pt-8 lg:px-10">
        <div className="mx-auto max-w-6xl space-y-5">
          {displayMessages.map((message, index) => (
            <MessageBubble
              key={message.id}
              message={message}
              index={index}
              onActionComplete={handleActionComplete}
            />
          ))}
          {editor.isTyping && <TypingIndicator />}
        </div>
      </div>

      <SmartInput onSend={editor.sendMessage} creationMode={creationMode} onCreationModeChange={setCreationMode} />
    </section>
  )
}
