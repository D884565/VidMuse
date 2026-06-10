import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./ProjectDetail.jsx', import.meta.url), 'utf8')

test('ProjectDetail applies a stable cache-busting token to the main project video', () => {
  assert.match(source, /import \{ appendVideoCacheBuster \} from '\.\.\/\.\.\/utils\/mediaUrl\.js'/)
  assert.match(source, /const \[projectSnapshot, setProjectSnapshot\] = useState\(project\)/)
  assert.match(source, /const displayVideoUrl = useMemo\(\s*\(\) => appendVideoCacheBuster\(videoUrl, projectSnapshot\.updated_at, projectSnapshot\.last_task_id\),/s)
  assert.match(source, /key=\{displayVideoUrl\}/)
  assert.match(source, /src=\{displayVideoUrl\}/)
})
