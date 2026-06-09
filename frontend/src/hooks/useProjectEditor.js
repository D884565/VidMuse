import { useCallback, useEffect, useRef } from 'react'
import { useChat } from './useChat.js'
import { useProjectPolling } from './useProjectPolling.js'
import { useAppStore } from '../store/appStore.js'
import { updateFrame, regenerateFrameImage, regenerateFrameVideo, regenerateFrame } from '../services/frame.js'
import { advanceWorkflowStage, confirmWorkflowStage, generateProjectScript } from '../services/project.js'

/**
 * 统一的项目编辑 hook，Chat 和 Canvas 共用。
 * 组合 useProjectPolling + useChat，提供统一的操作方法。
 */
export function useProjectEditor() {
  const activeProjectId = useAppStore((state) => state.activeProjectId)
  const polling = useProjectPolling(activeProjectId)
  const bumpProjectListVersion = useAppStore((state) => state.bumpProjectListVersion)
  const bumpConversationVersion = useAppStore((state) => state.bumpConversationVersion)
  const { applyFrameUpdates, applyProjectSnapshot, refetch } = polling
  const lastSyncedTaskRef = useRef(null)
  const lastStageStatusRef = useRef(null)

  const handleMessageHandled = useCallback(({ result } = {}) => {
    if (result?.updated_frames?.length) {
      applyFrameUpdates(result.updated_frames)
    }
    if (result?.workflow_stage || result?.stage_status || result?.task_id) {
      applyProjectSnapshot(result)
    }
    refetch()
    bumpProjectListVersion()
    bumpConversationVersion()
  }, [applyFrameUpdates, applyProjectSnapshot, bumpConversationVersion, bumpProjectListVersion, refetch])
  const chat = useChat({ onMessageHandled: handleMessageHandled })
  const reloadChat = chat.reload
  const projectLastTaskId = polling.project?.last_task_id || null
  const projectStageStatus = polling.project?.stage_status || null
  const projectWorkflowStage = polling.project?.workflow_stage || null

  useEffect(() => {
    if (!activeProjectId || !polling.project) return

    const currentStatus = projectStageStatus
    const previousStatus = lastStageStatusRef.current
    const taskId = projectLastTaskId
    lastStageStatusRef.current = currentStatus

    const finishedAsyncTask =
      taskId
      && previousStatus === 'running'
      && ['awaiting_review', 'failed'].includes(currentStatus)

    const completedWorkflow = projectWorkflowStage === 'completed' && taskId

    if (!finishedAsyncTask && !completedWorkflow) return
    if (lastSyncedTaskRef.current === `${taskId}:${currentStatus}:${projectWorkflowStage}`) return

    lastSyncedTaskRef.current = `${taskId}:${currentStatus}:${projectWorkflowStage}`
    reloadChat()
    bumpProjectListVersion()
    bumpConversationVersion()
  }, [
    activeProjectId,
    polling.project,
    projectLastTaskId,
    projectStageStatus,
    projectWorkflowStage,
    reloadChat,
    bumpConversationVersion,
    bumpProjectListVersion,
  ])

  // 统一的操作方法——Chat 和 Canvas 都调用这些
  const editFrame = async (frameId, patch) => {
    if (!activeProjectId) return
    await updateFrame(activeProjectId, frameId, patch)
    polling.refetch()
    chat.reload()
  }

  const doRegenerateFrameImage = async (frameId, instruction) => {
    if (!activeProjectId) return
    await regenerateFrameImage(activeProjectId, frameId, instruction || '')
    polling.refetch()
    chat.reload()
  }

  const doRegenerateFrameVideo = async (frameId, instruction) => {
    if (!activeProjectId) return
    await regenerateFrameVideo(activeProjectId, frameId, instruction || '')
    polling.refetch()
    chat.reload()
  }

  const doRegenerateFrame = async (frameId, instruction) => {
    if (!activeProjectId) return
    await regenerateFrame(activeProjectId, frameId, instruction || '')
    polling.refetch()
    chat.reload()
  }

  const doConfirmStage = async (stage) => {
    if (!activeProjectId) return
    await confirmWorkflowStage(activeProjectId, stage)
    polling.refetch()
    chat.reload()
  }

  const doAdvanceStage = async (confirmedStage) => {
    if (!activeProjectId) return
    await advanceWorkflowStage(activeProjectId, confirmedStage)
    polling.refetch()
    chat.reload()
  }

  const doGenerateScript = async (options = {}) => {
    if (!activeProjectId) return
    await generateProjectScript(activeProjectId, options)
    polling.refetch()
    chat.reload()
  }

  return {
    // 项目状态
    project: polling.project,
    frames: polling.frames,
    videoUrl: polling.videoUrl,
    audioUrl: polling.audioUrl,
    assets: polling.assets,
    loading: polling.loading,
    error: polling.error,
    refetch: polling.refetch,

    // 对话状态
    messages: chat.messages,
    isTyping: chat.isTyping,
    isThinking: chat.isThinking,
    historyLoaded: chat.historyLoaded,
    sendMessage: chat.sendMessage,
    reloadChat: chat.reload,

    // 统一操作
    editFrame,
    regenerateFrameImage: doRegenerateFrameImage,
    regenerateFrameVideo: doRegenerateFrameVideo,
    regenerateFrame: doRegenerateFrame,
    confirmStage: doConfirmStage,
    advanceStage: doAdvanceStage,
    generateScript: doGenerateScript,
  }
}
