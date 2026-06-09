const PROGRESS_MESSAGE_TRANSLATIONS = {
  'Project regeneration has been queued from chat.': '项目重生成任务已加入队列，稍后将继续处理。',
}

export function localizeProgressMessage(message) {
  if (typeof message !== 'string') {
    return message
  }

  return PROGRESS_MESSAGE_TRANSLATIONS[message] || message
}
