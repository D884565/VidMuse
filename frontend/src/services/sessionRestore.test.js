import test from 'node:test'
import assert from 'node:assert/strict'

import { restoreSession } from './sessionRestore.js'

test('restoreSession normalizes the current user info', async () => {
  const capturedConfigs = []
  const user = await restoreSession(
    async (config) => {
      capturedConfigs.push(config)
      return { id: 7, username: 'alice', role: 'admin' }
    },
    { timeoutMs: 25 }
  )

  assert.deepEqual(user, { id: 7, username: 'alice', role: 'admin' })
  assert.equal(capturedConfigs.length, 1)
  assert.equal(capturedConfigs[0]?.timeout, 25)
})

test('restoreSession rejects when loading the current user takes too long', async () => {
  await assert.rejects(
    () =>
      restoreSession(
        () => new Promise(() => {}),
        { timeoutMs: 20 }
      ),
    /登录恢复超时/
  )
})
