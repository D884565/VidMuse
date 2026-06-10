import MessageBlocks from './MessageBlocks.jsx'

export default function MessageBubble({ message, index, onActionComplete }) {
  const isUser = message.role === 'user'
  const isStreaming = message.streaming
  const hasRenderableContent = Boolean(
    (message.content || '').trim()
    || (message.blocks || []).length
    || message.progress
    || (message.updated_frames || []).length
  )

  if (!isUser && !hasRenderableContent) {
    return null
  }

  return (
    <article
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
      style={{ animation: `message-in 300ms ease-out ${index * 50}ms both` }}
    >
      <div
        className={`max-w-[72%] rounded-xl p-4 text-sm leading-6 ${
          isUser
            ? 'bg-[rgba(124,58,237,0.2)] text-white'
            : 'border-l-[3px] border-[#7c3aed] bg-[rgba(26,26,46,0.86)] text-white shadow-[0_4px_24px_rgba(124,58,237,0.08)]'
        }`}
      >
        <p className="m-0 whitespace-pre-wrap">
          {message.content}
          {isStreaming && <span className="inline-block w-[2px] h-[1em] bg-[#a78bfa] ml-[1px] align-text-bottom animate-pulse" />}
        </p>
        <MessageBlocks blocks={message.blocks || []} onActionComplete={onActionComplete} />
        {message.progress ? (
          <div className="mt-4">
            <div className="mb-2 flex justify-between text-xs text-[var(--text-muted)]">
              <span>视频生成中</span>
              <span>{message.progress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[rgba(148,163,184,0.14)]">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#7C3AED,#A855F7,#7C3AED)] bg-[length:200%_100%]"
                style={{
                  width: `${message.progress}%`,
                  animation: 'progress-flow 1.4s linear infinite',
                }}
              />
            </div>
          </div>
        ) : null}
        {/* 显示被更新的场景帧 */}
        {message.updated_frames && message.updated_frames.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.updated_frames.map((frame) => (
              <span
                key={frame.frame_id}
                className="inline-flex items-center gap-1 rounded-full bg-[rgba(124,58,237,0.15)] px-2.5 py-1 text-xs text-[#a78bfa]"
              >
                场景 {frame.sequence}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </article>
  )
}
