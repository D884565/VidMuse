import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./product.js', import.meta.url), 'utf8')

test('product service uses the existing /v1/products CRUD endpoints', () => {
  assert.match(source, /api\.get\('\/v1\/products', \{ params \}\)/)
  assert.match(source, /api\.post\('\/v1\/products', data\)/)
  assert.match(source, /api\.put\(`\/v1\/products\/\$\{productId\}`, data\)/)
  assert.match(source, /api\.delete\(`\/v1\/products\/\$\{productId\}`\)/)
})
