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
  buildScriptHistorySyncPlaceholder,
  buildScriptGenerationMessagePayload,
  clearPersistedDraftState,
  getProjectActivity,
  getProjectKey,
  getProjectMessages,
  mergeFetchedMessages,
  promoteDraftMessagesToProject,
  setProjectActivity,
  readPersistedDraftState,
  setProjectMessages,
  updateProjectMessage,
  writePersistedDraftState,
} from './chatState.js'

function buildScriptGenerationProgressBlock(status = 'running', taskId = null) {
  return {
    type: 'progress_card',
    stage: 'script',
    status,
    task_id: taskId,
    message: status === 'completed' ? '剧本创建完成' : '正在为您创建剧本...',
  }
}

export function useChat(options = {}) {
  const { onMessageHandled } = options
  const [messagesByProject, setMessagesByProject] = useState({})
  const [typingByProject, setTypingByProject] = useState({})
  const [thinkingByProject, setThinkingByProject] = useState({})
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const conversationVersion = useAppStore((state) => state.conversationVersion)
  const setActiveProjectId = useAppStore((state) => state.setActiveProjectId)
  const draftConversationTitle = useAppStore((state) => state.draftConversationTitle)
  const setDraftConversationTitle = useAppStore((state) => state.setDraftConversationTitle)
  const draftConversationMessages = useAppStore((state) => state.draftConversationMessages)
  const setDraftConversationMessages = useAppStore((state) => state.setDraftConversationMessages)
  const clearDraftConversation = useAppStore((state) => state.clearDraftConversation)
  const bumpProjectListVersion = useAppStore((state) => state.bumpProjectListVersion)
  const streamingIdRef = useRef(null)
  const streamingProjectKeyRef = useRef(null)
  const prevProjectIdRef = useRef(activeProjectId)

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
    const prevProjectId = prevProjectIdRef.current
    prevProjectIdRef.current = activeProjectId

    // 草稿模式：仅在从项目切回草稿时同步消息（sendMessage 已直接更新 messagesByProject）
    if (!activeProjectId) {
      if (prevProjectId !== activeProjectId && draftConversationMessages.length) {
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
          return setProjectMessages(
            current,
            projectKey,
            mergeFetchedMessages(existing, normalized)
          )
        })
        // 如果最后一条是用户消息且没有 assistant 回复，说明服务端还在处理
        if (normalized.length > 0) {
          const last = normalized[normalized.length - 1]
          if (last.role === 'user') {
            setThinkingByProject((current) => setProjectActivity(current, projectKey, true))
          } else {
            setThinkingByProject((current) => setProjectActivity(current, projectKey, false))
          }
        } else {
          setThinkingByProject((current) => setProjectActivity(current, projectKey, false))
        }
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
  }, [activeProjectId, reloadToken, conversationVersion])

  const sendMessage = useCallback(async (payload) => {
    const inputContent = typeof payload === 'string' ? payload : payload?.content || ''
    const selectedAssets = Array.isArray(payload?.selectedAssets) ? payload.selectedAssets : []
    const selectedProduct = payload?.selectedProduct || null
    const localRefs = Array.isArray(payload?.localRefs) ? payload.localRefs : []
    const creationMode = payload?.creationMode || null
    const submission = buildChatSubmission({
      content: inputContent,
      selectedAssets,
      selectedProduct,
      localRefs,
    })
    const trimmedContent = submission.displayContent.trim()
    if (!trimmedContent) return

    const clientUserId = crypto.randomUUID()
    const clientAssistantId = crypto.randomUUID()
    const normalizedLocalRefs = localRefs.map((ref) => ({
      id: ref.id,
      type: ref.type,
      url: ref.url || '',
      title: ref.title || '',
      content: ref.content || '',
      features: ref.features || null,
    }))
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
      local_references: normalizedLocalRefs,
      client_id: clientUserId,
      assistant_client_id: clientAssistantId,
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
        local_references: normalizedLocalRefs,
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
    setTypingByProject((current) => setProjectActivity(current, projectKey, true))

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
        setThinkingByProject((current) => setProjectActivity(current, projectKey, true))
      },
      onToken(data) {
        if (streamingIdRef.current !== assistantMsgId) return
        setThinkingByProject((current) => setProjectActivity(current, projectKey, false))
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
        setThinkingByProject((current) => setProjectActivity(current, projectKey, false))
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

      // 如果 entryResult 为 null（流异常关闭），清理 streaming 状态
      if (!entryResult) {
        setMessagesByProject((current) =>
          updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
            ...message,
            content: message.content || '请求未完成，请重试',
            streaming: false,
            optimistic: false,
          }))
        )
        updateDraftMessage((cache) =>
          updateProjectMessage(cache, projectKey, assistantMsgId, (message) => ({
            ...message,
            content: message.content || '请求未完成，请重试',
            streaming: false,
            optimistic: false,
          }))
        )
      }

      if (entryResult?.action === 'CREATE_PROJECT') {
        try {
          // 步骤1: 创建项目
          setMessagesByProject((current) =>
            updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
              ...message,
              content: '正在为您创建项目...',
              streaming: true,
            }))
          )
          const project = await createProject({
            user_prompt: submission.content,
            display_user_prompt: submission.displayContent,
            selected_assets: submission.selectedAssets,
            product_id: submission.selectedProduct?.id || null,
            style: useAppStore.getState().parameters?.style || null,
            voice_type: useAppStore.getState().parameters?.voice_type || null,
            auto_render: false,
          })
          projectId = project.id
          const draftProjectKey = projectKey
          projectKey = getProjectKey(projectId)
          clearDraftConversation()
          clearPersistedDraftState()
          bumpProjectListVersion()
          streamingIdRef.current = assistantMsgId
          streamingProjectKeyRef.current = projectKey
          setMessagesByProject((current) =>
            promoteDraftMessagesToProject(current, project.id, assistantMsgId)
          )
          setTypingByProject((current) => ({
            ...setProjectActivity(current, draftProjectKey, false),
            [projectKey]: true,
          }))
          setThinkingByProject((current) => setProjectActivity(current, draftProjectKey, false))
          setActiveProjectId(projectId)

          // 步骤2: 生成剧本
          setMessagesByProject((current) =>
            updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
              ...message,
              ...buildScriptGenerationMessagePayload('running'),
              streaming: true,
            }))
          )
          const scriptResult = await generateProjectScript(projectId, { creationMode })

          // 步骤3: 完成
          setMessagesByProject((current) =>
            updateProjectMessage(current, projectKey, assistantMsgId, (message) => ({
              ...message,
              ...buildScriptHistorySyncPlaceholder(scriptResult?.task_id || null),
              streaming: false,
              optimistic: false,
            }))
          )
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

    setTypingByProject((current) => setProjectActivity(current, projectKey, false))
    setThinkingByProject((current) => setProjectActivity(current, projectKey, false))
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

  const reload = useCallback(() => {
    setReloadToken((value) => value + 1)
  }, [])

  const messages = getProjectMessages(messagesByProject, activeProjectId)
  const isTyping = getProjectActivity(typingByProject, activeProjectId)
  const isThinking = getProjectActivity(thinkingByProject, activeProjectId)

  return {
    messages,
    isTyping,
    isThinking,
    sendMessage,
    historyLoaded,
    reload,
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
