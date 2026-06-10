import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./useChat.js', import.meta.url), { encoding: 'utf8' })

test('useChat scopes typing and thinking indicators by project key', () => {
  assert.match(source, /typingByProject/)
  assert.match(source, /thinkingByProject/)
  assert.match(source, /getProjectActivity\(typingByProject, activeProjectId\)/)
  assert.match(source, /getProjectActivity\(thinkingByProject, activeProjectId\)/)
  assert.doesNotMatch(source, /\[isTyping,\s*setIsTyping\]\s*=\s*useState\(false\)/)
  assert.doesNotMatch(source, /\[isThinking,\s*setIsThinking\]\s*=\s*useState\(false\)/)
  assert.doesNotMatch(source, /setIsTyping/)
  assert.doesNotMatch(source, /setIsThinking/)
})
