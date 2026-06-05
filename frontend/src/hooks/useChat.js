import { useCallback, useEffect, useState } from 'react'
import { sendChatMessage } from '../services/chat.js'
import { getConversations } from '../services/conversation.js'
import { createProject } from '../services/project.js'
import { useAppStore } from '../store/appStore.js'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)

  useEffect(() => {
    if (!activeProjectId) {
      setMessages([])
      setHistoryLoaded(true)
      return
    }

    let cancelled = false
    setHistoryLoaded(false)

    getConversations(activeProjectId)
      .then((conversations) => {
        if (cancelled) return
        setMessages((conversations || []).map(normalizeConversation))
      })
      .catch((err) => {
        console.warn('加载对话历史失败，使用空列表:', err.message)
        if (!cancelled) setMessages([])
      })
      .finally(() => {
        if (!cancelled) setHistoryLoaded(true)
      })

    return () => {
      cancelled = true
    }
  }, [activeProjectId, reloadToken])

  const sendMessage = useCallback(async (content) => {
    if (!content.trim()) return

    // 如果没有 activeProjectId，先自动创建项目
    let projectId = activeProjectId
    if (!projectId) {
      try {
        const project = await createProject({
          user_prompt: content.trim(),
          auto_render: false,
        })
        projectId = project.id
        setActiveProjectId(projectId)
      } catch (err) {
        setMessages((current) => [
          ...current,
          { id: crypto.randomUUID(), role: 'user', content: content.trim(), blocks: [] },
          { id: crypto.randomUUID(), role: 'assistant', content: `创建项目失败: ${err.message}`, blocks: [] },
        ])
        return
      }
    }

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', content: content.trim(), blocks: [] },
    ])
    setIsTyping(true)

    try {
      const result = await sendChatMessage(projectId, content.trim())
      const assistant = result.message || {}
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: assistant.content || 'Request processed.',
          blocks: assistant.blocks || [],
          stage: assistant.stage,
          action_type: assistant.action_type,
          task_id: assistant.task_id,
          updated_frames: result.updated_frames || [],
        },
      ])
    } catch (err) {
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: `请求失败: ${err.message}`, blocks: [] },
      ])
    } finally {
      setIsTyping(false)
    }
  }, [activeProjectId, setActiveProjectId])

  return {
    messages,
    isTyping,
    sendMessage,
    historyLoaded,
    reload: () => setReloadToken((value) => value + 1),
  }
}

function normalizeConversation(conversation) {
  return {
    id: conversation.id,
    role: conversation.role,
    content: conversation.content,
    message_type: conversation.message_type,
    stage: conversation.stage,
    blocks: conversation.blocks || [],
    action_type: conversation.action_type,
    task_id: conversation.task_id,
    metadata: conversation.metadata || {},
    frame_id: conversation.frame_id,
  }
}
