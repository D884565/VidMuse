import { WandSparkles } from 'lucide-react'
import { useChat } from '../../hooks/useChat.js'
import { useWorkflowProject } from '../../hooks/useWorkflowProject.js'
import { useAppStore } from '../../store/appStore.js'
import SmartInput from '../Input/SmartInput.jsx'
import StageProgress from '../Workflow/StageProgress.jsx'
import MessageBubble from './MessageBubble.jsx'
import TypingIndicator from './TypingIndicator.jsx'

export default function ChatContainer() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const { messages, isTyping, sendMessage, reload } = useChat()
  const { project, refetch } = useWorkflowProject(activeProjectId)

  function handleActionComplete() {
    reload()
    refetch()
  }

  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0 opacity-70 [background-image:radial-gradient(circle_at_12%_18%,rgba(56,189,248,0.16),transparent_26%),radial-gradient(circle_at_78%_4%,rgba(16,185,129,0.13),transparent_28%),linear-gradient(135deg,rgba(15,23,42,0.4),transparent)]" />

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
        <StageProgress project={project} />
      </header>

      <div className="relative z-10 flex-1 overflow-y-auto px-8 pb-44 pt-8">
        <div className="mx-auto max-w-5xl space-y-4">
          {!activeProjectId && (
            <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.03] p-8 text-center text-sm text-[var(--text-muted)]">
              先在左侧创建或选择一个项目，系统会把你的初始需求和素材渲染成第一条对话。
            </div>
          )}
          {messages.map((message, index) => (
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

      <SmartInput onSend={sendMessage} />
    </section>
  )
}
