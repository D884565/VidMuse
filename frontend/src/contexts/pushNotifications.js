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
  const description = payload.content?.message || payload.content

  notificationApi[level]({
    message: payload.title,
    description,
    duration: notificationDurations[level],
  })
}
