import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./CreateProjectModal.jsx', import.meta.url), 'utf8')

test('CreateProjectModal exposes only the supported voice choices', () => {
  assert.match(source, /zh_female_cancan_mars_bigtts/)
  assert.match(source, /zh_male_kailangxuezhang_uranus_bigtts/)
  assert.doesNotMatch(source, /zh_female_shuangkuai_moon_bigtts/)
  assert.doesNotMatch(source, /zh_male_chunhou_mars_bigtts/)
  assert.doesNotMatch(source, /zh_female_tianmei_mars_bigtts/)
  assert.doesNotMatch(source, /zh_male_yangguang_mars_bigtts/)
})
