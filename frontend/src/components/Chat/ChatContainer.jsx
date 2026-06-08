import { WandSparkles } from 'lucide-react'
import { useChat } from '../../hooks/useChat.js'
import { useProjectPolling } from '../../hooks/useProjectPolling.js'
import { useAppStore } from '../../store/appStore.js'
import SmartInput from '../Input/SmartInput.jsx'
import StageProgress from '../Workflow/StageProgress.jsx'
import MessageBubble from './MessageBubble.jsx'
import TypingIndicator from './TypingIndicator.jsx'

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content: `欢迎使用带货视频生成系统！我将帮助您一步步创建带货短视频：

1. 剧本创作 - 根据您的产品和需求生成分镜脚本
2. 分镜配图 - 为每个分镜生成精美的画面
3. 视频成片 - 将所有分镜合成为最终视频

请描述您想要推广的产品，或直接粘贴产品链接，我会为您开始创作。`,
}

export default function ChatContainer() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const { messages, isTyping, isThinking, sendMessage, reload } = useChat()
  const { project, refetch } = useProjectPolling(activeProjectId)

  function handleActionComplete() {
    reload()
    refetch()
  }

  const displayMessages = activeProjectId ? messages : [WELCOME_MESSAGE, ...messages]

  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0 opacity-70 [background-image:radial-gradient(circle_at_12%_18%,rgba(56,189,248,0.16),transparent 26%),radial-gradient(circle_at_78%_4%,rgba(16,185,129,0.13),transparent 28%),linear-gradient(135deg,rgba(15,23,42,0.4),transparent)]" />

      <header className="relative z-10 border-b border-[var(--border-soft)] px-8 py-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="m-0 text-lg font-semibold">对话式视频创作</h1>
            <p className="m-0 text-xs text-[var(--text-muted)]">
              通过对话推进剧本、图片、视频三个阶段
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-[var(--border-soft)] bg-[rgba(26,26,46,0.65)] px-3 py-1.5 text-xs text-[var(--text-muted)]">
            <WandSparkles size={14} className="text-[#38bdf8]" />
            工作流助手在线
          </div>
        </div>
        {activeProjectId && <StageProgress project={project} />}
      </header>

      <div className="relative z-10 flex-1 overflow-y-auto px-8 pb-44 pt-8">
        <div className="mx-auto max-w-5xl space-y-4">
          {displayMessages.map((message, index) => (
            <MessageBubble
              key={message.id}
              message={message}
              index={index}
              onActionComplete={handleActionComplete}
            />
          ))}
          {isTyping && <TypingIndicator />}
        </div>
      </div>

      {isThinking && (
        <div className="fixed bottom-24 left-1/2 z-50 -translate-x-1/2 text-xs text-[var(--text-muted)] animate-pulse">
          VidMuse 正在思考…
        </div>
      )}
      <SmartInput onSend={sendMessage} />
    </section>
  )
}
