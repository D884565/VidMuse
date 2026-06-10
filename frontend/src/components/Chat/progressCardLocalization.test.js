import test from 'node:test'
import assert from 'node:assert/strict'

test('localizeProgressMessage translates queued project regeneration copy into Chinese', async () => {
  const mod = await import('./progressCardLocalization.js').catch(() => null)

  assert.ok(mod?.localizeProgressMessage, 'localizeProgressMessage should be exported')
  assert.equal(
    mod.localizeProgressMessage('Project regeneration has been queued from chat.'),
    '项目重生成任务已加入队列，稍后将继续处理。'
  )
})

test('localizeProgressMessage leaves unrelated copy unchanged', async () => {
  const mod = await import('./progressCardLocalization.js').catch(() => null)

  assert.ok(mod?.localizeProgressMessage, 'localizeProgressMessage should be exported')
  assert.equal(
    mod.localizeProgressMessage('正在为您创建剧本...'),
    '正在为您创建剧本...'
  )
})
