import React, { createContext, useCallback, useContext, useEffect, useState, useRef } from 'react'
import { notification, message } from 'antd'
import { PushClient } from '@/utils/push-sdk'
import { showPushNotification } from './pushNotifications'

const PushContext = createContext()

export function PushProvider({ children }) {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState(null)
  const [pushClient, setPushClient] = useState(null)
  const [unreadCount, setUnreadCount] = useState(0)
  // 控制提示消息的显示，避免频繁弹出
  const [showReconnectTip, setShowReconnectTip] = useState(true)
  // 使用ref保存最新状态，避免作为useEffect依赖
  const showReconnectTipRef = useRef(showReconnectTip)
  // 消息去重集合，存储已处理的message_id
  const processedMessageIds = useRef(new Set())

  // 同步ref和state
  useEffect(() => {
    showReconnectTipRef.current = showReconnectTip
  }, [showReconnectTip])

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
    // 消息去重：如果有message_id且已经处理过，直接跳过
    if (msg.message_id) {
      if (processedMessageIds.current.has(msg.message_id)) {
        console.debug(`重复消息已跳过: ${msg.message_id}`)
        return
      }
      processedMessageIds.current.add(msg.message_id)
      // 定期清理去重集合，避免内存泄漏（保留最近1000条）
      if (processedMessageIds.current.size > 1000) {
        const oldestIds = Array.from(processedMessageIds.current).slice(0, 500)
        oldestIds.forEach(id => processedMessageIds.current.delete(id))
      }
    }

    // 全局消息提示
    if (msg.level && msg.title) {
      let content = msg.content?.message || msg.content
      // 确保content是字符串，避免React渲染对象错误
      if (typeof content === 'object' && content !== null) {
        // 优先提取错误消息
        if (content.error_message) {
          content = content.error_message
        } else if (content.message) {
          content = content.message
        } else if (content.status) {
          // 对于状态对象，显示状态和进度
          content = `状态: ${content.status}${content.progress !== undefined ? `，进度: ${content.progress}%` : ''}`
        } else {
          // 兜底：序列化对象
          content = JSON.stringify(content, null, 2)
        }
      }
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
      maxReconnectAttempts: 20,  // 增加最大重连次数
      reconnectInterval: 3000,
      heartbeatInterval: 30000,
      heartbeatTimeout: 15000,  // 延长心跳超时时间
    })

    client.onConnect(() => {
      setIsConnected(true)
      setError(null)
      notification.success({
        message: '实时推送服务已连接',
        duration: 3,
      })

      // 连接成功时清理部分旧的消息ID，避免内存占用过大
      if (processedMessageIds.current.size > 500) {
        const oldestIds = Array.from(processedMessageIds.current).slice(0, 250)
        oldestIds.forEach(id => processedMessageIds.current.delete(id))
      }

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
      if (code !== 1000 && showReconnectTipRef.current) { // 不是正常关闭，使用ref获取最新值
        message.warning('实时推送服务已断开，正在尝试重连...')
        // 30秒内不再显示重连提示
        setShowReconnectTip(false)
        setTimeout(() => setShowReconnectTip(true), 30000)
      }
    })

    client.onReconnectSuccess(() => {
      setIsConnected(true)
      setError(null)
      if (showReconnectTipRef.current) { // 使用ref获取最新值
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
  }, [handleMessage]) // 移除showReconnectTip依赖，避免循环创建连接

  const markMessagesAsRead = useCallback(async (messageIds) => {
    if (!pushClient) return undefined

    try {
      const res = await pushClient.markMessagesAsRead(messageIds)
      if (res.code === 200) {
        // 标记成功后重新获取最新的未读计数，确保准确性
        await refreshUnreadCount()
        return res
      }
      return res
    } catch (err) {
      console.error('标记消息已读失败:', err)
      throw err
    }
  }, [pushClient, refreshUnreadCount])

  const getHistoryMessages = useCallback(async (params = {}) => {
    if (!pushClient) return undefined

    try {
      return await pushClient.getHistoryMessages(params)
    } catch (err) {
      console.error('获取历史消息失败:', err)
      throw err
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
