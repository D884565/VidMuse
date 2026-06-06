import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./chat.js', import.meta.url), 'utf8')

test('chat service uses the backend /v1 chat stream routes consistently', () => {
  assert.doesNotMatch(source, /\/api\/generate\/v1\/projects\/\$\{projectId\}\/chat\/stream/)
  assert.doesNotMatch(source, /\/api\/generate\/v1\/chat\/entry\/stream/)
  assert.match(source, /sendSseChat\(`\/api\/v1\/projects\/\$\{projectId\}\/chat\/stream`, \{ content, frame_id: frameId \}, callbacks\)/)
  assert.match(source, /sendSseChat\('\/api\/v1\/chat\/entry\/stream', \{ content \}, callbacks\)/)
})
