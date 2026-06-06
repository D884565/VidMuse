import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./Sidebar.jsx', import.meta.url), 'utf8')

test('Sidebar imports Plus when rendering the create-project action', () => {
  assert.match(source, /import\s*\{[\s\S]*\bPlus\b[\s\S]*\}\s*from 'lucide-react'/)
  assert.match(source, /<Plus size=\{18\} \/>/)
})
