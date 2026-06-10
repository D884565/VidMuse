import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./ProjectManager.jsx', import.meta.url), 'utf8')

test('ProjectManager applies a cache-busting token to project preview videos', () => {
  assert.match(source, /import \{ appendVideoCacheBuster \} from '\.\.\/\.\.\/utils\/mediaUrl\.js'/)
  assert.match(source, /const displayVideoUrl = appendVideoCacheBuster\(project\.video_output_url, project\.updated_at, project\.last_task_id\)/)
  assert.match(source, /key=\{displayVideoUrl\}/)
  assert.match(source, /src=\{displayVideoUrl\}/)
})
