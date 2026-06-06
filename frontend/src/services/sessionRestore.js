function withTimeout(promise, timeoutMs) {
  if (!timeoutMs || timeoutMs <= 0) return promise

  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error('登录恢复超时')), timeoutMs)
    }),
  ])
}

export async function restoreSession(loadCurrentUser, options = {}) {
  const timeoutMs = options.timeoutMs ?? 8000
  const data = await withTimeout(loadCurrentUser({ timeout: timeoutMs }), timeoutMs)

  return {
    id: data.id,
    username: data.username,
    role: data.role,
  }
}
