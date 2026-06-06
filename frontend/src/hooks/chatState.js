export const DRAFT_PROJECT_KEY = '__draft__'

export function getProjectKey(projectId) {
  return projectId == null ? DRAFT_PROJECT_KEY : String(projectId)
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

export function mergeFetchedMessages(currentMessages, fetchedMessages, streamingMessageId = null) {
  const normalizedFetched = Array.isArray(fetchedMessages) ? fetchedMessages : []
  const optimisticMessages = (currentMessages || []).filter((message) => message?.optimistic)

  if (optimisticMessages.length === 0) {
    return normalizedFetched
  }

  const fetchedKeys = new Set(
    normalizedFetched.map((message) => getComparableMessageKey(message)).filter(Boolean)
  )

  const extraOptimisticMessages = optimisticMessages.filter((message) => {
    if (message.id === streamingMessageId) return true
    const comparableKey = getComparableMessageKey(message)
    return !comparableKey || !fetchedKeys.has(comparableKey)
  })

  return [...normalizedFetched, ...extraOptimisticMessages]
}

function getComparableMessageKey(message) {
  if (!message) return null
  const role = typeof message.role === 'string' ? message.role : ''
  const content = typeof message.content === 'string' ? message.content.trim() : ''
  if (!role || !content) return null
  return `${role}:${content}`
}
