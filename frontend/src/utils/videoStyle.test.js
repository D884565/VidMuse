import test from 'node:test'
import assert from 'node:assert/strict'

import { formatVideoStyle } from './videoStyle.js'

test('formatVideoStyle maps known english style keys to chinese labels', () => {
  assert.equal(formatVideoStyle('lifestyle'), '生活方式')
  assert.equal(formatVideoStyle('cinematic'), '电影感')
  assert.equal(formatVideoStyle('product'), '产品展示')
  assert.equal(formatVideoStyle('anime'), '动漫风')
  assert.equal(formatVideoStyle('realistic'), '写实风')
})

test('formatVideoStyle preserves unknown values and trims whitespace', () => {
  assert.equal(formatVideoStyle('  tech  '), '科技风')
  assert.equal(formatVideoStyle('custom-style'), 'custom-style')
  assert.equal(formatVideoStyle(''), '')
  assert.equal(formatVideoStyle(null), '')
})
