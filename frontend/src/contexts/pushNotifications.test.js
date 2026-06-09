import test from 'node:test'
import assert from 'node:assert/strict'

test('showPushNotification routes rich push payloads to the matching notification level', async () => {
  const mod = await import('./pushNotifications.js').catch(() => null)

  assert.ok(mod?.showPushNotification, 'showPushNotification should be exported')

  const calls = []
  const notification = {
    success(config) {
      calls.push(['success', config])
    },
    error(config) {
      calls.push(['error', config])
    },
    warning(config) {
      calls.push(['warning', config])
    },
    info(config) {
      calls.push(['info', config])
    },
  }

  mod.showPushNotification(notification, {
    level: 'error',
    title: 'Push failed',
    content: { message: 'Socket disconnected' },
  })

  assert.deepEqual(calls, [[
    'error',
    {
      message: 'Push failed',
      description: 'Socket disconnected',
      duration: 8,
    },
  ]])
})

test('showPushNotification ignores payloads without both level and title', async () => {
  const mod = await import('./pushNotifications.js').catch(() => null)

  assert.ok(mod?.showPushNotification, 'showPushNotification should be exported')

  const calls = []
  const notification = {
    success(config) {
      calls.push(['success', config])
    },
    error(config) {
      calls.push(['error', config])
    },
    warning(config) {
      calls.push(['warning', config])
    },
    info(config) {
      calls.push(['info', config])
    },
  }

  mod.showPushNotification(notification, {
    level: 'success',
    content: 'No title',
  })

  assert.deepEqual(calls, [])
})
