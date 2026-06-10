import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./api.js', import.meta.url), 'utf8')

test('api service refreshes tokens through the backend /v1 auth route', () => {
  assert.doesNotMatch(source, /\/api\/generate\/v1\/auth\/refresh/)
  assert.match(source, /\/api\/v1\/auth\/refresh/)
})
