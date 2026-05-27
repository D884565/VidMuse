import api from './api'

/**
 * 替换视频音频
 * @param {number} videoId - 视频素材 ID
 * @param {number} audioId - 音频素材 ID
 */
export async function replaceAudio(videoId, audioId) {
  return api.post('/v1/merge/audio-replace', { video_id: videoId, audio_id: audioId })
}

/**
 * 添加背景音乐
 * @param {number} videoId - 视频素材 ID
 * @param {number} bgmId - BGM 素材 ID
 * @param {number} bgmVolume - BGM 音量 (0-1)
 * @param {number} originalVolume - 原始音量 (0-1)
 */
export async function addBgm(videoId, bgmId, bgmVolume = 0.3, originalVolume = 1.0) {
  return api.post('/v1/merge/bgm', {
    video_id: videoId,
    bgm_id: bgmId,
    bgm_volume: bgmVolume,
    original_volume: originalVolume,
  })
}

/**
 * 混合多个音频轨道
 * @param {number} videoId - 视频素材 ID
 * @param {number[]} audioIds - 音频素材 ID 列表
 * @param {number[]} volumes - 各音频音量列表
 */
export async function mixAudio(videoId, audioIds, volumes) {
  return api.post('/v1/merge/mix', {
    video_id: videoId,
    audio_ids: audioIds,
    volumes,
  })
}

/**
 * 查询合成任务状态
 * @param {string} taskId - 任务 ID
 */
export async function getMergeTaskStatus(taskId) {
  return api.get(`/v1/merge/tasks/${taskId}`)
}

/**
 * 取消合成任务
 * @param {string} taskId - 任务 ID
 */
export async function cancelMergeTask(taskId) {
  return api.post(`/v1/merge/tasks/${taskId}/cancel`)
}
