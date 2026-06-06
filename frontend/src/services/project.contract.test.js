import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./project.js', import.meta.url), 'utf8')

test('generation task service paths accept string task ids without numeric coercion', () => {
  assert.match(source, /api\.get\(`\/v1\/tasks\/\$\{taskId\}`\)/)
  assert.match(source, /api\.get\(`\/v1\/tasks\/\$\{taskId\}\/steps`\)/)
  assert.doesNotMatch(source, /Number\(taskId\)|parseInt\(taskId/)
})
