import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./chat.js', import.meta.url), 'utf8')

test('chat service uses the backend /v1 chat stream routes consistently', () => {
  assert.doesNotMatch(source, /\/api\/generate\/v1\/projects\/\$\{projectId\}\/chat\/stream/)
  assert.doesNotMatch(source, /\/api\/generate\/v1\/chat\/entry\/stream/)
  assert.match(source, /sendSseChat\(`\/api\/v1\/projects\/\$\{projectId\}\/chat\/stream`, payload, callbacks\)/)
  assert.match(source, /sendSseChat\('\/api\/v1\/chat\/entry\/stream', payload, callbacks\)/)
})

test('chat service forwards extended payload fields for material-aware conversations', () => {
  assert.match(source, /export async function sendChatMessageStream\(projectId, payload, callbacks\)/)
  assert.match(source, /sendSseChat\(`\/api\/v1\/projects\/\$\{projectId\}\/chat\/stream`, payload, callbacks\)/)
  assert.match(source, /export async function sendEntryChatMessageStream\(payload, callbacks\)/)
  assert.match(source, /sendSseChat\('\/api\/v1\/chat\/entry\/stream', payload, callbacks\)/)
})
