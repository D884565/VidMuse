/**
 * WebSocket推送SDK
 * 提供统一的消息接收和处理接口
 */

class PushClient {
  /**
   * 构造函数
   * @param {Object} options - 配置选项
   * @param {string} options.wsUrl - WebSocket服务地址
   * @param {string} options.token - JWT认证令牌
   * @param {boolean} [options.autoReconnect=true] - 是否自动重连
   * @param {number} [options.maxReconnectAttempts=10] - 最大重连次数
   * @param {number} [options.reconnectInterval=3000] - 重连间隔（毫秒）
   * @param {number} [options.heartbeatInterval=30000] - 心跳间隔（毫秒）
   * @param {number} [options.heartbeatTimeout=10000] - 心跳超时时间（毫秒）
   */
  constructor(options) {
    this.options = {
      autoReconnect: true,
      maxReconnectAttempts: 10,
      reconnectInterval: 3000,
      heartbeatInterval: 30000,
      heartbeatTimeout: 10000,
      ...options
    }

    this.ws = null
    this.isConnected = false
    this.reconnectAttempts = 0
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.heartbeatTimeoutTimer = null

    // 事件监听器
    this.listeners = {
      message: [],
      messageType: {}, // 按消息类型分类的监听器
      error: [],
      disconnect: [],
      reconnectAttempt: [],
      reconnectSuccess: [],
      connect: []
    }
  }

  /**
   * 建立WebSocket连接
   */
  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      console.warn('WebSocket is already connecting or connected')
      return
    }

    const url = `${this.options.wsUrl}?token=${encodeURIComponent(this.options.token)}`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => this._onOpen()
    this.ws.onmessage = (event) => this._onMessage(event)
    this.ws.onerror = (error) => this._onError(error)
    this.ws.onclose = (event) => this._onClose(event)
  }

  /**
   * 断开连接
   */
  disconnect() {
    this._clearTimers()

    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect')
      this.ws = null
    }

    this.isConnected = false
    this.reconnectAttempts = 0
  }

  /**
   * 重新连接
   */
  reconnect() {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached')
      this._emit('disconnect', { code: 1008, reason: 'Max reconnection attempts reached' })
      return
    }

    this.reconnectAttempts++
    this._emit('reconnectAttempt', this.reconnectAttempts)

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, this.options.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1)) // 指数退避
  }

  /**
   * 监听所有消息
   * @param {Function} callback - 消息处理回调
   */
  onMessage(callback) {
    this.listeners.message.push(callback)
    return () => this._removeListener('message', callback)
  }

  /**
   * 监听特定类型的消息
   * @param {string} messageType - 消息类型
   * @param {Function} callback - 消息处理回调
   */
  onMessageType(messageType, callback) {
    if (!this.listeners.messageType[messageType]) {
      this.listeners.messageType[messageType] = []
    }
    this.listeners.messageType[messageType].push(callback)
    return () => this._removeMessageTypeListener(messageType, callback)
  }

  onTaskEvent(callback) {
    return this.onMessageType('task_event', callback)
  }

  /**
   * 监听错误事件
   * @param {Function} callback - 错误处理回调
   */
  onError(callback) {
    this.listeners.error.push(callback)
    return () => this._removeListener('error', callback)
  }

  /**
   * 监听连接断开事件
   * @param {Function} callback - 断开处理回调
   */
  onDisconnect(callback) {
    this.listeners.disconnect.push(callback)
    return () => this._removeListener('disconnect', callback)
  }

  /**
   * 监听重连尝试事件
   * @param {Function} callback - 重连尝试处理回调
   */
  onReconnectAttempt(callback) {
    this.listeners.reconnectAttempt.push(callback)
    return () => this._removeListener('reconnectAttempt', callback)
  }

  /**
   * 监听重连成功事件
   * @param {Function} callback - 重连成功处理回调
   */
  onReconnectSuccess(callback) {
    this.listeners.reconnectSuccess.push(callback)
    return () => this._removeListener('reconnectSuccess', callback)
  }

  /**
   * 监听连接成功事件
   * @param {Function} callback - 连接成功处理回调
   */
  onConnect(callback) {
    this.listeners.connect.push(callback)
    return () => this._removeListener('connect', callback)
  }

  /**
   * 获取历史消息
   * @param {Object} params - 查询参数
   * @returns {Promise} 消息列表
   */
  async getHistoryMessages(params = {}) {
    const queryParams = new URLSearchParams(params)
    const response = await fetch(`${this._getApiBaseUrl()}/v1/messages?${queryParams}`, {
      headers: {
        'Authorization': `Bearer ${this.options.token}`
      }
    })
    return response.json()
  }

  /**
   * 标记消息为已读
   * @param {Array<string>} messageIds - 消息ID列表
   * @returns {Promise} 操作结果
   */
  async markMessagesAsRead(messageIds) {
    const response = await fetch(`${this._getApiBaseUrl()}/v1/messages/read`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.options.token}`
      },
      body: JSON.stringify({ message_ids: messageIds })
    })
    return response.json()
  }

  /**
   * 获取未读消息数量
   * @returns {Promise} 未读数量
   */
  async getUnreadCount() {
    const response = await fetch(`${this._getApiBaseUrl()}/v1/messages/unread-count`, {
      headers: {
        'Authorization': `Bearer ${this.options.token}`
      }
    })
    return response.json()
  }

  /**
   * 连接成功处理
   */
  _onOpen() {
    this.isConnected = true
    const wasReconnecting = this.reconnectAttempts > 0
    this.reconnectAttempts = 0

    this._clearTimers()
    this._startHeartbeat()

    if (wasReconnecting) {
      this._emit('reconnectSuccess')
    } else {
      this._emit('connect')
    }
  }

  /**
   * 消息接收处理
   */
  _onMessage(event) {
    try {
      const message = JSON.parse(event.data)

      // 处理心跳响应
      if (message.type === 'pong') {
        this._handlePong()
        return
      }

      // 触发全局消息监听器
      this._emit('message', message)

      // 触发特定类型的消息监听器
      if (message.message_type && this.listeners.messageType[message.message_type]) {
        this.listeners.messageType[message.message_type].forEach(callback => {
          try {
            callback(message)
          } catch (error) {
            console.error('Message listener error:', error)
          }
        })
      }
    } catch (error) {
      console.error('Failed to parse message:', error)
    }
  }

  /**
   * 错误处理
   */
  _onError(error) {
    console.error('WebSocket error:', error)
    this._emit('error', error)
  }

  /**
   * 连接关闭处理
   */
  _onClose(event) {
    this.isConnected = false
    this._clearTimers()

    this._emit('disconnect', { code: event.code, reason: event.reason })

    // 自动重连
    if (this.options.autoReconnect && event.code !== 1000) { // 1000是正常关闭
      this.reconnect()
    }
  }

  /**
   * 启动心跳
   */
  _startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({
          type: 'ping',
          timestamp: Date.now()
        }))

        // 设置心跳超时
        this.heartbeatTimeoutTimer = setTimeout(() => {
          console.error('Heartbeat timeout')
          this.ws.close(1008, 'Heartbeat timeout')
        }, this.options.heartbeatTimeout)
      }
    }, this.options.heartbeatInterval)
  }

  /**
   * 处理心跳响应
   */
  _handlePong() {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer)
      this.heartbeatTimeoutTimer = null
    }
  }

  /**
   * 清除所有定时器
   */
  _clearTimers() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer)
      this.heartbeatTimeoutTimer = null
    }
  }

  /**
   * 触发事件
   */
  _emit(eventName, ...args) {
    if (this.listeners[eventName]) {
      this.listeners[eventName].forEach(callback => {
        try {
          callback(...args)
        } catch (error) {
          console.error(`Event listener error for ${eventName}:`, error)
        }
      })
    }
  }

  _removeListener(eventName, callback) {
    if (!this.listeners[eventName]) {
      return
    }
    this.listeners[eventName] = this.listeners[eventName].filter(listener => listener !== callback)
  }

  _removeMessageTypeListener(messageType, callback) {
    if (!this.listeners.messageType[messageType]) {
      return
    }
    this.listeners.messageType[messageType] = this.listeners.messageType[messageType].filter(
      listener => listener !== callback
    )
    if (!this.listeners.messageType[messageType].length) {
      delete this.listeners.messageType[messageType]
    }
  }

  /**
   * 获取API基础地址
   */
  _getApiBaseUrl() {
    // 从WebSocket地址推断API地址
    const url = new URL(this.options.wsUrl)
    const protocol = url.protocol === 'wss:' ? 'https:' : 'http:'
    return `${protocol}//${url.host}`
  }
}

export default PushClient
export { PushClient }
