import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./project.js', import.meta.url), 'utf8')

test('project service uses the backend /v1/projects routes consistently', () => {
  assert.doesNotMatch(source, /\/generate\/v1\/projects/)
  assert.match(source, /api\.get\('\/v1\/projects', \{ params \}\)/)
  assert.match(source, /api\.get\(`\/v1\/projects\/\$\{projectId\}`\)/)
  assert.match(source, /api\.put\(`\/v1\/projects\/\$\{projectId\}`, data\)/)
  assert.match(source, /api\.delete\(`\/v1\/projects\/\$\{projectId\}`\)/)
})
