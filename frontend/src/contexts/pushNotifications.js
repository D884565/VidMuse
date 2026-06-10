const notificationDurations = {
  success: 5,
  error: 8,
  warning: 6,
  info: 5,
}

export function showPushNotification(notificationApi, payload) {
  if (!payload?.level || !payload?.title) {
    return
  }

  const level = notificationDurations[payload.level] ? payload.level : 'info'
  let description = payload.content?.message || payload.content
  // 确保description是字符串，避免React渲染对象错误
  if (typeof description === 'object' && description !== null) {
    // 优先提取错误消息
    if (description.error_message) {
      description = description.error_message
    } else if (description.message) {
      description = description.message
    } else if (description.status) {
      // 对于状态对象，显示状态和进度
      description = `状态: ${description.status}${description.progress !== undefined ? `，进度: ${description.progress}%` : ''}`
    } else {
      // 兜底：序列化对象
      description = JSON.stringify(description, null, 2)
    }
  }

  notificationApi[level]({
    message: payload.title,
    description,
    duration: notificationDurations[level],
  })
}
