/** 为 Promise 添加超时控制 */
function withTimeout(promise, timeoutMs) {
  if (!timeoutMs || timeoutMs <= 0) return promise

  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error('登录恢复超时')), timeoutMs)
    }),
  ])
}

/** 恢复登录会话 — 调用用户信息接口，超时则自动登出 */
export async function restoreSession(loadCurrentUser, options = {}) {
  const timeoutMs = options.timeoutMs ?? 8000
  const data = await withTimeout(loadCurrentUser({ timeout: timeoutMs }), timeoutMs)

  return {
    id: data.id,
    username: data.username,
    role: data.role,
  }
}
