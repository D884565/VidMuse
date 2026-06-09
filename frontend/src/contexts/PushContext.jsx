import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { PushClient } from '@/utils/push-sdk'
import { message } from 'antd'

const PushContext = createContext()

export function PushProvider({ children }) {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState(null)
  const [pushClient, setPushClient] = useState(null)
  const [unreadCount, setUnreadCount] = useState(0)
  // 控制提示消息的显示，避免频繁弹出
  const [showReconnectTip, setShowReconnectTip] = useState(true)

  // 刷新未读数量
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

  // 处理消息
  const handleMessage = useCallback((msg) => {
    // 全局消息提示
    if (msg.level && msg.title) {
      const content = msg.content?.message || msg.content
      switch (msg.level) {
        case 'success':
          message.success({
            content: msg.title,
            description: content,
            duration: 5
          })
          break
        case 'error':
          message.error({
            content: msg.title,
            description: content,
            duration: 8
          })
          break
        case 'warning':
          message.warning({
            content: msg.title,
            description: content,
            duration: 6
          })
          break
        default:
          message.info({
            content: msg.title,
            description: content,
            duration: 5
          })
      }
    }

    // 更新未读数量 - 离线消息已经在数据库中统计过，不需要重复增加
    if (msg.message_type !== 'system' && !msg.offline) {
      setUnreadCount(prev => prev + 1)
    }
  }, [])

  // 初始化推送客户端
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
      maxReconnectAttempts: 20,  // 增加最大重连次数
      reconnectInterval: 3000,
      heartbeatInterval: 30000,
      heartbeatTimeout: 15000,  // 延长心跳超时时间
    })

    client.onConnect(() => {
      setIsConnected(true)
      setError(null)
      message.success('实时推送服务已连接')

      // 获取未读消息数量
      client.getUnreadCount().then(res => {
        if (res.code === 200) {
          setUnreadCount(res.data.unread_count)
        }
      }).catch(err => {
        console.error('获取未读消息数量失败:', err)
      })
    })

    client.onDisconnect(({ code, reason }) => {
      setIsConnected(false)
      setError(new Error(`连接断开: ${reason || code}`))
      if (code !== 1000 && showReconnectTip) { // 不是正常关闭
        message.warning('实时推送服务已断开，正在尝试重连...')
        // 30秒内不再显示重连提示
        setShowReconnectTip(false)
        setTimeout(() => setShowReconnectTip(true), 30000)
      }
    })

    client.onReconnectSuccess(() => {
      setIsConnected(true)
      setError(null)
      if (showReconnectTip) {
        message.success('实时推送服务已重新连接')
        // 重连成功后重置提示状态
        setShowReconnectTip(true)
      }
    })

    client.onError((err) => {
      console.error('WebSocket错误:', err)
      setError(err)
    })

    client.onMessage(handleMessage)

    client.connect()
    setPushClient(client)

    return () => {
      client.disconnect()
    }
  }, [handleMessage, showReconnectTip])

  // 标记消息为已读
  const markMessagesAsRead = useCallback(async (messageIds) => {
    if (!pushClient) return

    try {
      const res = await pushClient.markMessagesAsRead(messageIds)
      if (res.code === 200) {
        // 标记成功后重新获取最新的未读计数，确保准确性
        await refreshUnreadCount()
        return res
      }
    } catch (err) {
      console.error('标记消息已读失败:', err)
      throw err
    }
  }, [pushClient, refreshUnreadCount])

  // 获取历史消息
  const getHistoryMessages = useCallback(async (params = {}) => {
    if (!pushClient) return

    try {
      const res = await pushClient.getHistoryMessages(params)
      return res
    } catch (err) {
      console.error('获取历史消息失败:', err)
      throw err
    }
  }, [pushClient])

  return (
    <PushContext.Provider value={{
      isConnected,
      error,
      pushClient,
      unreadCount,
      markMessagesAsRead,
      getHistoryMessages,
      refreshUnreadCount
    }}>
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
