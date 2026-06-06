import { useCallback, useEffect, useRef, useState } from 'react'
import { sendChatMessageStream, sendEntryChatMessageStream } from '../services/chat.js'
import { getConversations } from '../services/conversation.js'
import { createProject } from '../services/project.js'
import { useAppStore } from '../store/appStore.js'
import {
  appendOptimisticMessages,
  appendTokenToMessage,
  getProjectKey,
  getProjectMessages,
  mergeFetchedMessages,
  promoteDraftMessagesToProject,
  setProjectMessages,
  updateProjectMessage,
} from './chatState.js'

export function useChat(options = {}) {
  const { onMessageHandled } = options
  const [messagesByProject, setMessagesByProject] = useState({})
  const [isTyping, setIsTyping] = useState(false)
  const [isThinking, setIsThinking] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const setDraftConversationTitle = useAppStore((state) => state.setDraftConversationTitle)
  const clearDraftConversation = useAppStore((state) => state.clearDraftConversation)
  const bumpProjectListVersion = useAppStore((state) => state.bumpProjectListVersion)
  const streamingIdRef = useRef(null)
  const streamingProjectKeyRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    const projectKey = getProjectKey(activeProjectId)

    if (!activeProjectId) {
      setHistoryLoaded(true)
      return () => {
        cancelled = true
      }
    }

    setHistoryLoaded(false)

    getConversations(activeProjectId)
      .then((conversations) => {
        if (cancelled) return
        const normalized = (conversations || []).map(normalizeConversation)
        setMessagesByProject((current) => {
          const existing = getProjectMessages(current, projectKey)
          const streamingMessageId = streamingProjectKeyRef.current === projectKey ? streamingIdRef.current : null
          return setProjectMessages(
            current,
            projectKey,
            mergeFetchedMessages(existing, normalized, streamingMessageId)
          )
        })
      })
      .catch((err) => {
        console.warn('鍔犺浇瀵硅瘽鍘嗗彶澶辫触锛屼娇鐢ㄧ┖鍒楄〃:', err.message)
        if (!cancelled) {
          setMessagesByProject((current) => setProjectMessages(current, projectKey, []))
        }
      })
      .finally(() => {
        if (!cancelled) setHistoryLoaded(true)
      })

    return () => {
      cancelled = true
    }
  }, [activeProjectId, reloadToken])

  const sendMessage = useCallback(async (content) => {
    const trimmedContent = content.trim()
    if (!trimmedContent) return

    let projectId = activeProjectId
    let projectKey = getProjectKey(projectId)

    const userMsgId = crypto.randomUUID()
    const assistantMsgId = crypto.randomUUID()
    streamingIdRef.current = assistantMsgId
    streamingProjectKeyRef.current = projectKey

    setMessagesByProject((current) =>
      appendOptimisticMessages(current, projectKey, {
        userMessage: { id: userMsgId, role: 'user', content: trimmedContent, blocks: [], optimistic: true },
        assistantMessage: { id: assistantMsgId, role: 'assistant', content: '', blocks: [], streaming: true, optimistic: true },
      })
    )
    setIsTyping(true)

    let finalResult = null
    let entryResult = null

    const callbacks = {
      onStart() {},
      onThinking() {
        if (streamingIdRef.current !== assistantMsgId) return
        setIsThinking(true)
      },
      onToken(data) {
        if (streamingIdRef.current !== assistantMsgId) return
        setIsThinking(false)
        setMessagesByProject((current) =>
          appendTokenToMessage(current, projectKey, assistantMsgId, data.content || '')
        )
      },
      onBlocks(data) {
        if (streamingIdRef.current !== assistantMsgId) return
        setMessagesByProject((current) =>
          updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
            ...message,
            blocks: data.blocks || [],
            stage: data.stage,
            task_id: data.task_id,
          }))
        )
      },
      onDone(data) {
        finalResult = data
        entryResult = data
        if (streamingIdRef.current !== assistantMsgId) return
        setMessagesByProject((current) =>
          updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
            ...message,
            streaming: false,
            optimistic: false,
            action_type: data.action,
            should_create_project: data.should_create_project,
            task_id: data.task_id,
            updated_frames: data.updated_frames || [],
          }))
        )
      },
      onError(err) {
        setIsThinking(false)
        setMessagesByProject((current) =>
          updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
            ...message,
            content: message.content || `璇锋眰澶辫触: ${err.message}`,
            streaming: false,
            optimistic: false,
          }))
        )
      },
    }

    if (!projectId) {
      setDraftConversationTitle(trimmedContent)
      await sendEntryChatMessageStream(trimmedContent, callbacks)
      if (entryResult?.action === 'CREATE_PROJECT') {
        try {
          const project = await createProject({
            user_prompt: trimmedContent,
            auto_render: false,
          })
          projectId = project.id
          projectKey = getProjectKey(projectId)
          clearDraftConversation()
          bumpProjectListVersion()
          streamingIdRef.current = assistantMsgId
          streamingProjectKeyRef.current = projectKey
          setMessagesByProject((current) =>
            promoteDraftMessagesToProject(current, project.id, assistantMsgId)
          )
          setActiveProjectId(projectId)
          await sendChatMessageStream(projectId, trimmedContent, null, callbacks)
        } catch (err) {
          setMessagesByProject((current) =>
            updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
              ...message,
              content: `鍒涘缓椤圭洰澶辫触: ${err.message}`,
              streaming: false,
              optimistic: false,
            }))
          )
        }
      }
    } else {
      await sendChatMessageStream(projectId, trimmedContent, null, callbacks)
    }

    setIsTyping(false)
    streamingIdRef.current = null
    streamingProjectKeyRef.current = null

    if (finalResult && projectId) {
      onMessageHandled?.({ projectId, result: finalResult })
    }
  }, [activeProjectId, bumpProjectListVersion, clearDraftConversation, onMessageHandled, setActiveProjectId, setDraftConversationTitle])

  const messages = getProjectMessages(messagesByProject, activeProjectId)

  return {
    messages,
    isTyping,
    isThinking,
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
