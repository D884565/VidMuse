import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./Sidebar.jsx', import.meta.url), 'utf8')

test('Sidebar wires new chat button to the draft conversation store actions', () => {
  assert.match(source, /const setActiveProjectId = useAppStore\(\(state\) => state\.setActiveProjectId\)/)
  assert.match(source, /const clearDraftConversation = useAppStore\(\(state\) => state\.clearDraftConversation\)/)
  assert.match(source, /onClick=\{\(\) => \{\s*setActiveProjectId\(null\)\s*clearDraftConversation\(\)\s*setActiveView\('chat'\)/s)
})
