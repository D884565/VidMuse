import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./Sidebar.jsx', import.meta.url), 'utf8')

test('Sidebar renders a products navigation button wired to activeView', () => {
  assert.match(source, /activeView === 'products'/)
  assert.match(source, /setActiveView\('products'\)/)
})

test('Sidebar removes the bottom create-project action and uses an account menu entry for profile', () => {
  assert.doesNotMatch(source, /<Plus size=\{18\} \/>/)
  assert.doesNotMatch(source, /activeView === 'profile'/)
  assert.match(source, /setProfileMenuOpen\(\(open\) => !open\)/)
  assert.match(source, /setActiveView\('profile'\)/)
})
