import test from 'node:test'
import assert from 'node:assert/strict'

import { normalizeProductPayload } from './productFormUtils.js'

test('normalizeProductPayload trims strings and converts blank price to null', () => {
  const payload = normalizeProductPayload({
    name: '  夏日防晒喷雾  ',
    brand: '  VidMuse  ',
    price: '',
    main_image_url: ' https://example.com/a.png ',
    description: '  清爽防晒  ',
  })

  assert.deepEqual(payload, {
    name: '夏日防晒喷雾',
    brand: 'VidMuse',
    price: null,
    main_image_url: 'https://example.com/a.png',
    description: '清爽防晒',
  })
})
