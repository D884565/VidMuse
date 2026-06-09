import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { notification } from 'antd'
import { PushClient } from '@/utils/push-sdk'
import { showPushNotification } from './pushNotifications'

const PushContext = createContext()

export function PushProvider({ children }) {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState(null)
  const [pushClient, setPushClient] = useState(null)
  const [unreadCount, setUnreadCount] = useState(0)

  const handlePushMessage = useCallback((pushMessage) => {
    showPushNotification(notification, pushMessage)

    if (pushMessage.message_type !== 'system') {
      setUnreadCount((prev) => prev + 1)
    }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setError(new Error('未登录，无法连接推送服务'))
      return undefined
    }

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
      notification.success({
        message: '实时推送服务已连接',
        duration: 3,
      })

      client.getUnreadCount()
        .then((res) => {
          if (res.code === 200) {
            setUnreadCount(res.data.unread_count)
          }
        })
        .catch((err) => {
          console.error('获取未读消息数量失败:', err)
        })
    })

    client.onDisconnect(({ code, reason }) => {
      setIsConnected(false)
      setError(new Error(`连接断开: ${reason || code}`))
      if (code !== 1000) {
        notification.warning({
          message: '实时推送服务已断开，正在尝试重连...',
          duration: 4,
        })
      }
    })

    client.onReconnectSuccess(() => {
      setIsConnected(true)
      setError(null)
      notification.success({
        message: '实时推送服务已重新连接',
        duration: 3,
      })
    })

    client.onError((err) => {
      console.error('WebSocket错误:', err)
      setError(err)
    })

    client.onMessage(handlePushMessage)

    client.connect()
    setPushClient(client)

    return () => {
      client.disconnect()
    }
  }, [handlePushMessage])

  const markMessagesAsRead = useCallback(async (messageIds) => {
    if (!pushClient) return undefined

    try {
      const res = await pushClient.markMessagesAsRead(messageIds)
      if (res.code === 200) {
        setUnreadCount((prev) => Math.max(0, prev - messageIds.length))
        return res
      }
      return res
    } catch (err) {
      console.error('标记消息已读失败:', err)
      throw err
    }
  }, [pushClient])

  const getHistoryMessages = useCallback(async (params = {}) => {
    if (!pushClient) return undefined

    try {
      return await pushClient.getHistoryMessages(params)
    } catch (err) {
      console.error('获取历史消息失败:', err)
      throw err
    }
  }, [pushClient])

  const refreshUnreadCount = useCallback(async () => {
    if (!pushClient) return

    try {
      const res = await pushClient.getUnreadCount()
      if (res.code === 200) {
        setUnreadCount(res.data.unread_count)
      }
    } catch (err) {
      console.error('刷新未读数量失败:', err)
    }
  }, [pushClient])

  return (
    <PushContext.Provider
      value={{
        isConnected,
        error,
        pushClient,
        unreadCount,
        markMessagesAsRead,
        getHistoryMessages,
        refreshUnreadCount,
      }}
    >
      {children}
    </PushContext.Provider>
  )
}

export function usePush() {
  const context = useContext(PushContext)
  if (!context) {
    throw new Error('usePush must be used within a PushProvider')
  }
  return context
}

export default PushContext
