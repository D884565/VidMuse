import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./UserProfile.jsx', import.meta.url), 'utf8')

test('UserProfile keeps editable account information and password update actions', () => {
  assert.match(source, /updateUserInfo\(\{ username: username\.trim\(\) \}\)/)
  assert.match(source, /changePassword\(oldPassword, newPassword\)/)
  assert.match(source, /个人信息/)
})
