import { useState } from 'react'

const initialMessages = [
  {
    id: 'm-001',
    role: 'assistant',
    content:
      '告诉我你想创作的视频主题、风格和使用场景。我可以帮你生成脚本、分镜和视频参数。',
  },
  {
    id: 'm-002',
    role: 'user',
    content: '帮我做一个 10 秒的新品发布短视频，画面要有科技感。',
  },
  {
    id: 'm-003',
    role: 'assistant',
    content:
      '已设置为 16:9、10s、电影感风格。你可以继续补充产品卖点，也可以直接发送开始生成。',
    progress: 64,
  },
]

export function useChat() {
  const [messages, setMessages] = useState(initialMessages)
  const [isTyping, setIsTyping] = useState(false)

  function sendMessage(content, files = []) {
    if (!content.trim() && files.length === 0) return

    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: 'user',
        content: content.trim() || '已上传素材',
        files,
      },
    ])
    setIsTyping(true)

    window.setTimeout(() => {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '收到。我会基于你的描述整理视频生成方案，并保留当前参数设置。',
        },
      ])
      setIsTyping(false)
    }, 900)
  }

  return { messages, isTyping, sendMessage }
}
