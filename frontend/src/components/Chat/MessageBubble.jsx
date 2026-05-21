export default function MessageBubble({ message, index }) {
  const isUser = message.role === 'user'

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
        <p className="m-0 whitespace-pre-wrap">{message.content}</p>
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
      </div>
    </article>
  )
}
