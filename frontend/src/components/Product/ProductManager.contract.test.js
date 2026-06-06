import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { filterOwnedProducts } from './productFormUtils.js'

test('filterOwnedProducts keeps only non-public products', () => {
  const result = filterOwnedProducts([
    { id: 1, name: '用户商品A', is_public: false },
    { id: 2, name: '公共商品B', is_public: true },
    { id: 3, name: '用户商品C' },
  ])

  assert.deepEqual(result.map((item) => item.id), [1, 3])
})

test('ProductManager wires delete confirmation and refreshes the list afterwards', () => {
  const source = readFileSync(new URL('./ProductManager.jsx', import.meta.url), 'utf8')
  assert.match(source, /ConfirmDialog/)
  assert.match(source, /await deleteProduct\(productId\)/)
  assert.match(source, /await fetchProducts\(\)/)
})
