import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DRAFT_PROJECT_KEY,
  appendOptimisticMessages,
  appendTokenToMessage,
  getProjectMessages,
  mergeFetchedMessages,
} from './chatState.js'

test('mergeFetchedMessages keeps optimistic messages while the assistant is still streaming', () => {
  const projectKey = '101'
  const optimisticCache = appendOptimisticMessages({}, projectKey, {
    userMessage: { id: 'user-local', role: 'user', content: 'make a short ad', blocks: [], optimistic: true },
    assistantMessage: { id: 'assistant-local', role: 'assistant', content: 'Thinking', blocks: [], streaming: true, optimistic: true },
  })

  const merged = mergeFetchedMessages(
    getProjectMessages(optimisticCache, projectKey),
    [{ id: 1, role: 'assistant', content: 'older reply', blocks: [] }],
    'assistant-local'
  )

  assert.equal(merged.length, 3)
  assert.equal(merged.at(-2)?.id, 'user-local')
  assert.equal(merged.at(-1)?.id, 'assistant-local')
  assert.equal(merged.at(-1)?.streaming, true)
})

test('mergeFetchedMessages deduplicates the optimistic user copy once persisted history has it', () => {
  const projectKey = '101'
  const optimisticCache = appendOptimisticMessages({}, projectKey, {
    userMessage: { id: 'user-local', role: 'user', content: 'make a short ad', blocks: [], optimistic: true },
    assistantMessage: { id: 'assistant-local', role: 'assistant', content: '', blocks: [], streaming: true, optimistic: true },
  })

  const merged = mergeFetchedMessages(
    getProjectMessages(optimisticCache, projectKey),
    [
      { id: 1, role: 'assistant', content: 'older reply', blocks: [] },
      { id: 2, role: 'user', content: 'make a short ad', blocks: [] },
    ],
    'assistant-local'
  )

  const matchingUsers = merged.filter((message) => message.role === 'user' && message.content === 'make a short ad')
  assert.equal(matchingUsers.length, 1)
  assert.equal(merged.at(-1)?.id, 'assistant-local')
})

test('appendTokenToMessage updates only the originating project cache', () => {
  const projectOne = '101'
  const projectTwo = '202'
  let cache = appendOptimisticMessages({}, projectOne, {
    userMessage: { id: 'user-local', role: 'user', content: 'hello', blocks: [], optimistic: true },
    assistantMessage: { id: 'assistant-local', role: 'assistant', content: '', blocks: [], streaming: true, optimistic: true },
  })
  cache = {
    ...cache,
    [projectTwo]: [{ id: 'other-project-message', role: 'assistant', content: 'keep me', blocks: [] }],
  }

  const updated = appendTokenToMessage(cache, projectOne, 'assistant-local', ' world')

  assert.equal(updated[projectOne].at(-1)?.content, ' world')
  assert.deepEqual(updated[projectTwo], cache[projectTwo])
  assert.equal(getProjectMessages(updated, DRAFT_PROJECT_KEY).length, 0)
})
