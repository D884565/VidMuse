import { useCallback, useEffect, useRef, useState } from 'react'
import { sendChatMessageStream, sendEntryChatMessageStream } from '../services/chat.js'
import { getConversations } from '../services/conversation.js'
import { createProject, generateProjectScript } from '../services/project.js'
import { buildChatSubmission } from '../components/Input/materialPrompt.js'
import { useAppStore } from '../store/appStore.js'
import {
  DRAFT_PROJECT_KEY,
  appendOptimisticMessages,
  appendTokenToMessage,
  clearPersistedDraftState,
  getProjectKey,
  getProjectMessages,
  mergeFetchedMessages,
  promoteDraftMessagesToProject,
  readPersistedDraftState,
  setProjectMessages,
  updateProjectMessage,
  writePersistedDraftState,
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
  const draftConversationTitle = useAppStore((state) => state.draftConversationTitle)
  const setDraftConversationTitle = useAppStore((state) => state.setDraftConversationTitle)
  const draftConversationMessages = useAppStore((state) => state.draftConversationMessages)
  const setDraftConversationMessages = useAppStore((state) => state.setDraftConversationMessages)
  const clearDraftConversation = useAppStore((state) => state.clearDraftConversation)
  const bumpProjectListVersion = useAppStore((state) => state.bumpProjectListVersion)
  const streamingIdRef = useRef(null)
  const streamingProjectKeyRef = useRef(null)

  useEffect(() => {
    const persistedDraft = readPersistedDraftState()
    if (!persistedDraft) return

    if (persistedDraft.title) {
      setDraftConversationTitle(persistedDraft.title)
    }
    if (persistedDraft.messages?.length) {
      setDraftConversationMessages(persistedDraft.messages)
      setMessagesByProject((current) =>
        setProjectMessages(current, DRAFT_PROJECT_KEY, persistedDraft.messages)
      )
    }
  }, [setDraftConversationMessages, setDraftConversationTitle])

  useEffect(() => {
    if (draftConversationTitle || draftConversationMessages.length) {
      writePersistedDraftState(null, {
        title: draftConversationTitle,
        messages: draftConversationMessages,
      })
      return
    }
    clearPersistedDraftState()
  }, [draftConversationMessages, draftConversationTitle])

  useEffect(() => {
    let cancelled = false
    const projectKey = getProjectKey(activeProjectId)

    if (!activeProjectId) {
      if (draftConversationMessages.length) {
        setMessagesByProject((current) =>
          setProjectMessages(current, projectKey, draftConversationMessages)
        )
      }
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
          const streamingMessageId =
            streamingProjectKeyRef.current === projectKey ? streamingIdRef.current : null
          return setProjectMessages(
            current,
            projectKey,
            mergeFetchedMessages(existing, normalized, streamingMessageId)
          )
        })
      })
      .catch((err) => {
        console.warn('加载会话历史失败:', err.message)
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
  }, [activeProjectId, draftConversationMessages, reloadToken])

  const sendMessage = useCallback(async (payload) => {
    const inputContent = typeof payload === 'string' ? payload : payload?.content || ''
    const selectedAssets = Array.isArray(payload?.selectedAssets) ? payload.selectedAssets : []
    const selectedProduct = payload?.selectedProduct || null
    const submission = buildChatSubmission({
      content: inputContent,
      selectedAssets,
      selectedProduct,
    })
    const trimmedContent = submission.displayContent.trim()
    if (!trimmedContent) return

    const clientUserId = crypto.randomUUID()
    const clientAssistantId = crypto.randomUUID()
    const requestPayload = {
      content: submission.content,
      display_content: submission.displayContent,
      selected_assets: submission.selectedAssets,
      selected_product: submission.selectedProduct ? {
        id: submission.selectedProduct.id,
        name: submission.selectedProduct.name,
        brand: submission.selectedProduct.brand,
        price: submission.selectedProduct.price,
        description: submission.selectedProduct.description,
        main_image_url: submission.selectedProduct.main_image_url,
      } : null,
      client_id: clientUserId,
    }

    let projectId = activeProjectId
    let projectKey = getProjectKey(projectId)

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmedContent,
      blocks: [],
      optimistic: true,
      client_id: clientUserId,
      metadata: {
        client_id: clientUserId,
        display_content: trimmedContent,
        selected_assets: submission.selectedAssets,
        selected_product: submission.selectedProduct,
      },
    }
    const assistantMsgId = crypto.randomUUID()
    const assistantMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      blocks: [],
      streaming: true,
      optimistic: true,
      client_id: clientAssistantId,
    }

    streamingIdRef.current = assistantMsgId
    streamingProjectKeyRef.current = projectKey

    setMessagesByProject((current) =>
      appendOptimisticMessages(current, projectKey, {
        userMessage,
        assistantMessage,
      })
    )
    if (!projectId) {
      setDraftConversationMessages((currentDraftMessages) => {
        const nextDraft = appendOptimisticMessages(
          { [DRAFT_PROJECT_KEY]: currentDraftMessages },
          projectKey,
          { userMessage, assistantMessage }
        )
        return nextDraft[DRAFT_PROJECT_KEY] || []
      })
    }
    setIsTyping(true)

    let finalResult = null
    let entryResult = null

    const updateDraftMessage = (updater) => {
      if (projectId) return
      setDraftConversationMessages((currentDraftMessages) => {
        const nextDraft = updater({ [DRAFT_PROJECT_KEY]: currentDraftMessages })
        return nextDraft[DRAFT_PROJECT_KEY] || []
      })
    }

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
        updateDraftMessage((cache) =>
          appendTokenToMessage(cache, projectKey, assistantMsgId, data.content || '')
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
        updateDraftMessage((cache) =>
          updateProjectMessage(cache, projectKey, assistantMsgId, (message) => ({
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
            metadata: {
              ...(message.metadata || {}),
              client_id: clientAssistantId,
            },
          }))
        )
        updateDraftMessage((cache) =>
          updateProjectMessage(cache, projectKey, assistantMsgId, (message) => ({
            ...message,
            streaming: false,
            optimistic: false,
            action_type: data.action,
            should_create_project: data.should_create_project,
            task_id: data.task_id,
            updated_frames: data.updated_frames || [],
            metadata: {
              ...(message.metadata || {}),
              client_id: clientAssistantId,
            },
          }))
        )
      },
      onError(err) {
        setIsThinking(false)
        setMessagesByProject((current) =>
          updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
            ...message,
            content: message.content || `请求失败: ${err.message}`,
            streaming: false,
            optimistic: false,
          }))
        )
        updateDraftMessage((cache) =>
          updateProjectMessage(cache, projectKey, assistantMsgId, (message) => ({
            ...message,
            content: message.content || `请求失败: ${err.message}`,
            streaming: false,
            optimistic: false,
          }))
        )
      },
    }

    if (!projectId) {
      setDraftConversationTitle(trimmedContent)
      await sendEntryChatMessageStream(requestPayload, callbacks)
      if (entryResult?.action === 'CREATE_PROJECT') {
        try {
          const project = await createProject({
            user_prompt: submission.content,
            selected_assets: submission.selectedAssets,
            auto_render: false,
          })
          projectId = project.id
          projectKey = getProjectKey(projectId)
          clearDraftConversation()
          clearPersistedDraftState()
          bumpProjectListVersion()
          streamingIdRef.current = assistantMsgId
          streamingProjectKeyRef.current = projectKey
          setMessagesByProject((current) =>
            promoteDraftMessagesToProject(current, project.id, assistantMsgId)
          )
          setActiveProjectId(projectId)
          const scriptResult = await generateProjectScript(projectId)
          setReloadToken((value) => value + 1)
          onMessageHandled?.({ projectId, result: scriptResult })
        } catch (err) {
          setMessagesByProject((current) =>
            updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
              ...message,
              content: `创建项目失败: ${err.message}`,
              streaming: false,
              optimistic: false,
            }))
          )
        }
      }
    } else {
      await sendChatMessageStream(projectId, requestPayload, callbacks)
    }

    setIsTyping(false)
    streamingIdRef.current = null
    streamingProjectKeyRef.current = null

    if (finalResult && projectId) {
      onMessageHandled?.({ projectId, result: finalResult })
    }
  }, [
    activeProjectId,
    bumpProjectListVersion,
    clearDraftConversation,
    onMessageHandled,
    setActiveProjectId,
    setDraftConversationMessages,
    setDraftConversationTitle,
  ])

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
  const displayContent = typeof conversation.metadata?.display_content === 'string'
    ? conversation.metadata.display_content
    : conversation.content
  return {
    id: conversation.id,
    role: conversation.role,
    content: displayContent,
    message_type: conversation.message_type,
    stage: conversation.stage,
    blocks: conversation.blocks || [],
    action_type: conversation.action_type,
    task_id: conversation.task_id,
    metadata: conversation.metadata || {},
    frame_id: conversation.frame_id,
    client_id: conversation.metadata?.client_id,
  }
}
