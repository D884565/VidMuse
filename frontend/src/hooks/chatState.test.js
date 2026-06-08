import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DRAFT_PROJECT_KEY,
  appendOptimisticMessages,
  appendTokenToMessage,
  clearPersistedDraftState,
  getProjectMessages,
  getProjectActivity,
  mergeFetchedMessages,
  readPersistedDraftState,
  setProjectActivity,
  writePersistedDraftState,
} from './chatState.js'

test('mergeFetchedMessages keeps optimistic messages while the assistant is still streaming', () => {
  const projectKey = '101'
  const optimisticCache = appendOptimisticMessages({}, projectKey, {
    userMessage: { id: 'user-local', role: 'user', content: 'make a short ad', blocks: [], optimistic: true },
    assistantMessage: { id: 'assistant-local', role: 'assistant', content: 'Thinking', blocks: [], streaming: true, optimistic: true },
  })

  const merged = mergeFetchedMessages(
    getProjectMessages(optimisticCache, projectKey),
    [{ id: 1, role: 'assistant', content: 'older reply', blocks: [] }]
  )

  // user-local 没有 client_id，服务端也没有相同 role+content，所以保留
  // assistant-local 没有 client_id，服务端 content 不同，所以保留
  assert.equal(merged.length, 3)
  assert.equal(merged[0]?.id, 1)
  assert.equal(merged[1]?.id, 'user-local')
  assert.equal(merged[2]?.id, 'assistant-local')
  assert.equal(merged[2]?.streaming, true)
})

test('draft conversation state can be persisted and restored', () => {
  const storage = new Map()
  const draftState = {
    title: '生成一个热水壶带货视频',
    messages: [
      { id: 'user-1', role: 'user', content: '生成一个热水壶带货视频', blocks: [] },
      { id: 'assistant-1', role: 'assistant', content: '我来先帮你整理卖点。', blocks: [] },
    ],
  }

  const localStorage = {
    getItem(key) {
      return storage.has(key) ? storage.get(key) : null
    },
    setItem(key, value) {
      storage.set(key, value)
    },
    removeItem(key) {
      storage.delete(key)
    },
  }

  clearPersistedDraftState(localStorage)
  assert.equal(readPersistedDraftState(localStorage), null)

  writePersistedDraftState(localStorage, draftState)
  assert.deepEqual(readPersistedDraftState(localStorage), draftState)

  clearPersistedDraftState(localStorage)
  assert.equal(readPersistedDraftState(localStorage), null)
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
    ]
  )

  // user-local 通过 role+content 匹配到服务端 id=2，被去重
  // assistant-local content='' 不匹配任何服务端消息，保留
  const matchingUsers = merged.filter((message) => message.role === 'user' && message.content === 'make a short ad')
  assert.equal(matchingUsers.length, 1)
  assert.equal(merged.at(-1)?.id, 'assistant-local')
})

test('mergeFetchedMessages replaces optimistic messages with persisted server ids when metadata links them', () => {
  const projectKey = '101'
  const optimisticCache = appendOptimisticMessages({}, projectKey, {
    userMessage: {
      id: 'user-local',
      role: 'user',
      content: 'make a short ad',
      blocks: [],
      optimistic: true,
      client_id: 'client-user-1',
    },
    assistantMessage: {
      id: 'assistant-local',
      role: 'assistant',
      content: 'Queued',
      blocks: [],
      streaming: true,
      optimistic: true,
      client_id: 'client-assistant-1',
    },
  })

  const merged = mergeFetchedMessages(
    getProjectMessages(optimisticCache, projectKey),
    [
      {
        id: 11,
        role: 'user',
        content: 'make a short ad',
        blocks: [],
        metadata: { client_id: 'client-user-1' },
      },
      {
        id: 12,
        role: 'assistant',
        content: 'Queued',
        blocks: [],
        metadata: { client_id: 'client-assistant-1' },
      },
    ]
  )

  assert.equal(merged.length, 2)
  assert.equal(merged[0]?.id, 11)
  assert.equal(merged[1]?.id, 12)
  assert.equal(merged.some((message) => message.id === 'user-local'), false)
  assert.equal(merged.some((message) => message.id === 'assistant-local'), false)
})

test('mergeFetchedMessages keeps local generated script message during stale history refresh', () => {
  const projectKey = '54'
  const localMessages = [
    {
      id: 'assistant-local',
      role: 'assistant',
      content: '剧本已生成！您可以在右侧分镜面板中查看和调整。',
      blocks: [{ type: 'storyboard_table', frames: [{ id: 1 }] }],
      streaming: false,
      optimistic: false,
      client_id: 'client-assistant-54',
      stage: 'script',
      action_type: 'GENERATE_SCRIPT',
    },
  ]

  const merged = mergeFetchedMessages(
    localMessages,
    [
      { id: 336, role: 'assistant', content: '欢迎使用带货视频生成系统！', blocks: [] },
      { id: 337, role: 'user', content: '生成这个洗面奶带货视频', blocks: [] },
    ]
  )

  assert.equal(merged.length, 3)
  assert.equal(merged.at(-1)?.id, 'assistant-local')
  assert.equal(merged.at(-1)?.blocks?.[0]?.type, 'storyboard_table')

  const refreshed = mergeFetchedMessages(
    merged,
    [
      { id: 336, role: 'assistant', content: '欢迎使用带货视频生成系统！', blocks: [] },
      { id: 337, role: 'user', content: '生成这个洗面奶带货视频', blocks: [] },
      {
        id: 338,
        role: 'assistant',
        content: '剧本阶段已完成。请检查主题、风格和每个分镜内容，满意后可以确认并生成图片。',
        blocks: [{ type: 'storyboard_table', frames: [{ id: 1 }] }],
        stage: 'script',
        action_type: 'GENERATE_SCRIPT',
      },
    ]
  )

  assert.equal(refreshed.length, 3)
  assert.equal(refreshed.at(-1)?.id, 338)
})

test('mergeFetchedMessages removes orphan optimistic assistant when persisted content already exists', () => {
  const projectKey = '101'
  const optimisticCache = appendOptimisticMessages({}, projectKey, {
    userMessage: {
      id: 'user-local',
      role: 'user',
      content: '继续',
      blocks: [],
      optimistic: true,
      client_id: 'client-user-orphan',
    },
    assistantMessage: {
      id: 'assistant-local',
      role: 'assistant',
      content: '好的，已确认剧本，正在生成分镜图片。',
      blocks: [{ type: 'progress_card', stage: 'image' }],
      optimistic: true,
      client_id: 'client-assistant-orphan',
    },
  })

  const merged = mergeFetchedMessages(
    getProjectMessages(optimisticCache, projectKey),
    [
      {
        id: 41,
        role: 'user',
        content: '继续',
        blocks: [],
      },
      {
        id: 42,
        role: 'assistant',
        content: '好的，已确认剧本，正在生成分镜图片。',
        blocks: [{ type: 'progress_card', stage: 'image' }],
      },
    ]
  )

  assert.equal(merged.length, 2)
  assert.equal(merged.some((message) => message.id === 'assistant-local'), false)
  assert.equal(merged[1]?.id, 42)
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

test('project activity flags are isolated per project', () => {
  const activity = setProjectActivity({}, '101', true)

  assert.equal(getProjectActivity(activity, '101'), true)
  assert.equal(getProjectActivity(activity, '202'), false)
  assert.equal(getProjectActivity(activity, DRAFT_PROJECT_KEY), false)

  const cleared = setProjectActivity(activity, '101', false)
  assert.equal(getProjectActivity(cleared, '101'), false)
})

test('mergeFetchedMessages prefers metadata display content while deduplicating optimistic user messages by client id', () => {
  const projectKey = '303'
  const optimisticCache = appendOptimisticMessages({}, projectKey, {
    userMessage: {
      id: 'user-local',
      role: 'user',
      content: '做一条夏日防晒喷雾带货视频',
      blocks: [],
      optimistic: true,
      client_id: 'client-user-303',
      metadata: { display_content: '做一条夏日防晒喷雾带货视频' },
    },
    assistantMessage: {
      id: 'assistant-local',
      role: 'assistant',
      content: '',
      blocks: [],
      streaming: true,
      optimistic: true,
      client_id: 'client-assistant-303',
    },
  })

  const merged = mergeFetchedMessages(
    getProjectMessages(optimisticCache, projectKey),
    [
      {
        id: 31,
        role: 'user',
        content: '做一条夏日防晒喷雾带货视频\n\n参考素材：\n1. [图片] 防晒喷雾主图（asset_id: 101）',
        blocks: [],
        metadata: {
          client_id: 'client-user-303',
          display_content: '做一条夏日防晒喷雾带货视频',
        },
      },
    ]
  )

  assert.equal(merged.length, 2)
  assert.equal(merged[0]?.id, 31)
  assert.equal(merged[0]?.content, '做一条夏日防晒喷雾带货视频')
  assert.equal(merged[0]?.metadata?.display_content, '做一条夏日防晒喷雾带货视频')
  assert.equal(merged[1]?.id, 'assistant-local')
})
