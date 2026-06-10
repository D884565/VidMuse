import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./ProjectList.jsx', import.meta.url), 'utf8')

test('ProjectList renders saved projects inside a fixed-height scroll area', () => {
  assert.match(source, /max-h-\[\s*calc\(5\s*\*\s*4\.75rem\)\s*\]/)
  assert.match(source, /overflow-y-auto/)
})
