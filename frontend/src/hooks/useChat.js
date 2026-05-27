import { useState, useCallback } from 'react'
import { sendChatMessage } from '../services/chat.js'
import { useAppStore } from '../store/appStore.js'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const activeProjectId = useAppStore((state) => state.activeProjectId)

  const sendMessage = useCallback(async (content, files = []) => {
    if (!content.trim() && files.length === 0) return
    if (!activeProjectId) return

    // 添加用户消息
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', content: content.trim() || '已上传素材', files },
    ])
    setIsTyping(true)

    try {
      const result = await sendChatMessage(activeProjectId, content.trim())
      // 添加 assistant 回复
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: result.message || '已处理您的请求',
          updated_frames: result.updated_frames || [],
        },
      ])
    } catch (err) {
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: `请求失败: ${err.message}` },
      ])
    } finally {
      setIsTyping(false)
    }
  }, [activeProjectId])

  return { messages, isTyping, sendMessage }
}
