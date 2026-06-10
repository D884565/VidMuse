import { useEffect, useCallback } from 'react'
import { usePush } from '@/contexts/PushContext'

export function usePipelinePush({ onUpdate } = {}) {
  const { isConnected, error, pushClient } = usePush()

  // 处理消息更新
  const handlePipelineMessage = useCallback((message) => {
    if (message.message_type === 'pipeline_execution_update' && onUpdate) {
      onUpdate(message.content)
    }
  }, [onUpdate])

  useEffect(() => {
    if (!pushClient) return

    // 添加特定类型的消息监听器
    const removeListener = pushClient.onMessageType('pipeline_execution_update', handlePipelineMessage)

    return () => {
      removeListener()
    }
  }, [pushClient, handlePipelineMessage])

  return {
    isConnected,
    error,
    pushClient
  }
}
