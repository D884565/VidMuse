import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./MessageBlocks.jsx', import.meta.url), 'utf8')

test('MessageBlocks applies a stable cache-busting token to full video cards', () => {
  assert.match(source, /import \{ appendVideoCacheBuster \} from '\.\.\/\.\.\/utils\/mediaUrl\.js'/)
  assert.match(source, /const displayVideoUrl = appendVideoCacheBuster\(block\.video_url, block\.updated_at, block\.task_id\)/)
  assert.match(source, /key=\{displayVideoUrl\}/)
  assert.match(source, /src=\{displayVideoUrl\}/)
})
