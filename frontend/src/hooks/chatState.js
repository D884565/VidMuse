export const DRAFT_PROJECT_KEY = '__draft__'
const DRAFT_STORAGE_KEY = 'vidmuse:draft-conversation'

export function getProjectKey(projectId) {
  return projectId == null ? DRAFT_PROJECT_KEY : String(projectId)
}

function resolveStorage(storage) {
  if (storage) return storage
  if (typeof globalThis === 'undefined') return null
  return globalThis.localStorage || null
}

export function readPersistedDraftState(storage) {
  const targetStorage = resolveStorage(storage)
  if (!targetStorage) return null

  try {
    const rawValue = targetStorage.getItem(DRAFT_STORAGE_KEY)
    if (!rawValue) return null
    const parsed = JSON.parse(rawValue)
    return {
      title: typeof parsed?.title === 'string' ? parsed.title : '',
      messages: Array.isArray(parsed?.messages) ? parsed.messages : [],
    }
  } catch {
    return null
  }
}

export function writePersistedDraftState(storage, draftState) {
  const targetStorage = resolveStorage(storage)
  if (!targetStorage) return

  const normalizedState = {
    title: typeof draftState?.title === 'string' ? draftState.title : '',
    messages: Array.isArray(draftState?.messages) ? draftState.messages : [],
  }

  if (!normalizedState.title && normalizedState.messages.length === 0) {
    clearPersistedDraftState(targetStorage)
    return
  }

  try {
    targetStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(normalizedState))
  } catch {
    // Ignore local persistence failures and keep the in-memory draft.
  }
}

export function clearPersistedDraftState(storage) {
  const targetStorage = resolveStorage(storage)
  if (!targetStorage) return

  try {
    targetStorage.removeItem(DRAFT_STORAGE_KEY)
  } catch {
    // Ignore local persistence failures and keep the in-memory draft.
  }
}

export function getProjectMessages(cache, projectId) {
  return cache[getProjectKey(projectId)] || []
}

export function setProjectMessages(cache, projectId, messages) {
  return {
    ...cache,
    [getProjectKey(projectId)]: messages,
  }
}

export function getProjectActivity(activityByProject, projectId) {
  return Boolean(activityByProject[getProjectKey(projectId)])
}

export function setProjectActivity(activityByProject, projectId, active) {
  return {
    ...activityByProject,
    [getProjectKey(projectId)]: Boolean(active),
  }
}

export function appendOptimisticMessages(cache, projectId, { userMessage, assistantMessage }) {
  const projectKey = getProjectKey(projectId)
  const currentMessages = cache[projectKey] || []
  return {
    ...cache,
    [projectKey]: [...currentMessages, userMessage, assistantMessage],
  }
}

export function updateProjectMessage(cache, projectId, messageId, updater) {
  const projectKey = getProjectKey(projectId)
  const currentMessages = cache[projectKey] || []
  const index = currentMessages.findIndex((message) => message.id === messageId)
  if (index === -1) return cache

  const nextMessages = [...currentMessages]
  nextMessages[index] = updater(nextMessages[index])
  return {
    ...cache,
    [projectKey]: nextMessages,
  }
}

export function appendTokenToMessage(cache, projectId, messageId, content) {
  return updateProjectMessage(cache, projectId, messageId, (message) => ({
    ...message,
    content: `${message.content || ''}${content || ''}`,
  }))
}

export function buildScriptGenerationMessagePayload(status = 'running', taskId = null) {
  const normalizedStatus = String(status || 'running').toLowerCase()
  const isCompleted = normalizedStatus === 'completed'
  return {
    content: isCompleted ? '剧本创建完成' : '好的，正在为您生成剧本，请稍候~',
    blocks: [
      {
        type: 'progress_card',
        stage: 'script',
        status,
        task_id: taskId,
        message: isCompleted ? '剧本创建完成' : '正在为您创建剧本...',
      },
    ],
  }
}

export function promoteDraftMessagesToProject(cache, projectId, streamingMessageId = null) {
  const projectKey = getProjectKey(projectId)
  const draftMessages = cache[DRAFT_PROJECT_KEY] || []
  const migratedMessages = draftMessages.map((message) => (
    message.id === streamingMessageId
      ? { ...message, content: '', blocks: [], streaming: true, optimistic: true }
      : { ...message, optimistic: true }
  ))

  return {
    ...cache,
    [projectKey]: migratedMessages,
    [DRAFT_PROJECT_KEY]: [],
  }
}

export function mergeFetchedMessages(currentMessages, fetchedMessages) {
  const normalizedFetched = normalizeFetchedMessages(Array.isArray(fetchedMessages) ? fetchedMessages : [])
  const localMessages = (currentMessages || []).filter((message) => shouldKeepLocalMessage(message))

  if (localMessages.length === 0) {
    return normalizedFetched.sort((a, b) => getSortId(a) - getSortId(b))
  }

  const fetchedKeys = new Set(
    normalizedFetched.map((message) => getComparableMessageKey(message)).filter(Boolean)
  )
  const fetchedContentKeys = new Set(
    normalizedFetched.map((message) => getContentMessageKey(message)).filter(Boolean)
  )
  const fetchedActionKeys = new Set(
    normalizedFetched.map((message) => getActionMessageKey(message)).filter(Boolean)
  )

  const extraLocalMessages = localMessages.filter((message) => {
    const comparableKey = getComparableMessageKey(message)
    // 如果服务端已有相同消息（通过 client_id 或 role+content 匹配），过滤掉乐观消息
    if (comparableKey && fetchedKeys.has(comparableKey)) return false
    const contentKey = getContentMessageKey(message)
    if (contentKey && fetchedContentKeys.has(contentKey)) return false
    const actionKey = getActionMessageKey(message)
    if (actionKey && fetchedActionKeys.has(actionKey)) return false
    return !comparableKey || !fetchedKeys.has(comparableKey)
  })

  const merged = [...normalizedFetched, ...extraLocalMessages]
  return merged.sort((a, b) => getSortId(a) - getSortId(b))
}

function shouldKeepLocalMessage(message) {
  if (!message) return false
  if (message.optimistic || message.streaming) return true
  const id = message.id
  const isServerId = typeof id === 'number' || (typeof id === 'string' && id.trim() !== '' && !Number.isNaN(Number(id)))
  return !isServerId && Boolean(message.client_id || message.metadata?.client_id)
}

function getComparableMessageKey(message) {
  if (!message) return null
  const clientId = message.client_id || message.metadata?.client_id
  if (clientId) return `client:${clientId}`
  return getContentMessageKey(message)
}

function getActionMessageKey(message) {
  if (!message) return null
  const role = typeof message.role === 'string' ? message.role : ''
  const actionType = typeof message.action_type === 'string' ? message.action_type : ''
  const stage = typeof message.stage === 'string' ? message.stage : ''
  if (role !== 'assistant' || !actionType || !stage) return null
  return `${role}:${stage}:${actionType}`
}

function getContentMessageKey(message) {
  if (!message) return null
  const role = typeof message.role === 'string' ? message.role : ''
  // 优先用 _original_content（保留了服务端原始 content），其次用 content（可能被替换为 display_content）
  const content = typeof message._original_content === 'string'
    ? message._original_content.trim()
    : typeof message.content === 'string'
      ? message.content.trim()
      : ''
  if (!role || !content) return null
  return `${role}:${content}`
}

function normalizeFetchedMessages(messages) {
  return messages.map((message) => {
    const displayContent = typeof message?.metadata?.display_content === 'string'
      ? message.metadata.display_content.trim()
      : ''
    if (!displayContent) return message
    return {
      ...message,
      content: displayContent,
      // 保留原始 content 用于去重（display_content 可能与原始 content 不同）
      _original_content: message.content,
    }
  })
}

function getSortId(message) {
  const id = message?.id
  if (typeof id === 'number') return id
  if (typeof id === 'string') {
    // 尝试解析为数字（服务端返回的数字 ID）
    const parsed = Number(id)
    if (!Number.isNaN(parsed)) return parsed
    // UUID 字符串：提取时间相关部分作为排序依据，确保乐观消息排在最后
    return Infinity
  }
  return Infinity
}
