import { useEffect, useState, useCallback } from 'react'
import { PushClient } from '@/utils/push-sdk'

export function usePipelinePush({ onUpdate } = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState(null)
  const [pushClient, setPushClient] = useState(null)

  // 处理消息更新
  const handleMessage = useCallback((message) => {
    if (message.message_type === 'pipeline_execution_update' && onUpdate) {
      onUpdate(message.content)
    }
  }, [onUpdate])

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setError(new Error('未登录，无法连接推送服务'))
      return
    }

    // 使用相对路径走Vite代理，避免跨域问题
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/ws/connect`

    const client = new PushClient({
      wsUrl,
      token,
      autoReconnect: true,
      maxReconnectAttempts: 10,
      reconnectInterval: 3000,
      heartbeatInterval: 30000,
    })

    client.onConnect(() => {
      setIsConnected(true)
      setError(null)
    })

    client.onDisconnect(({ code, reason }) => {
      setIsConnected(false)
      setError(new Error(`连接断开: ${reason || code}`))
    })

    client.onError((err) => {
      setError(err)
    })

    client.onMessage(handleMessage)

    client.connect()
    setPushClient(client)

    return () => {
      client.disconnect()
    }
  }, [handleMessage])

  return {
    isConnected,
    error,
    pushClient
  }
}
