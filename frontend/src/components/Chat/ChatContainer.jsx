import { WandSparkles } from 'lucide-react'
import { useChat } from '../../hooks/useChat.js'
import SmartInput from '../Input/SmartInput.jsx'
import MessageBubble from './MessageBubble.jsx'
import TypingIndicator from './TypingIndicator.jsx'

export default function ChatContainer() {
  const { messages, isTyping, sendMessage } = useChat()

  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:radial-gradient(circle_at_20%_20%,rgba(124,58,237,0.16),transparent_28%),radial-gradient(circle_at_80%_0%,rgba(168,85,247,0.12),transparent_24%)]" />

      <header className="relative z-10 flex h-16 items-center justify-between border-b border-[var(--border-soft)] px-8">
        <div>
          <h1 className="m-0 text-lg font-semibold">智能视频生成</h1>
          <p className="m-0 text-xs text-[var(--text-muted)]">
            对话驱动脚本、分镜、素材与参数配置
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-[var(--border-soft)] bg-[rgba(26,26,46,0.65)] px-3 py-1.5 text-xs text-[var(--text-muted)]">
          <WandSparkles size={14} className="text-[#a78bfa]" />
          生成服务已就绪
        </div>
      </header>

      <div className="relative z-10 flex-1 overflow-y-auto px-8 pb-44 pt-8">
        <div className="mx-auto max-w-4xl space-y-4">
          {messages.map((message, index) => (
            <MessageBubble key={message.id} message={message} index={index} />
          ))}
          {isTyping && <TypingIndicator />}
        </div>
      </div>

      <SmartInput onSend={sendMessage} />
    </section>
  )
}
