# 音视频处理 API 接口文档

## 概述

音视频处理模块提供视频分段和音视频合成功能，服务于 RAG 模块和视频生成模块。

## 视频处理接口

### 1. 获取视频信息

**接口**: `GET /v1/video/{video_id}/info`

**描述**: 获取视频文件的元数据信息（时长、分辨率、格式等）

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video_id` | Integer | 是 | 视频资产ID |

**响应示例**:

```json
{
  "code": "0000000",
  "message": "success",
  "data": {
    "video_id": 1,
    "duration": 10.5,
    "width": 1920,
    "height": 1080,
    "format": "mp4",
    "file_size": 1024000,
    "fps": 30.0
  }
}
```

**错误码**:

| 错误码 | 说明 |
|--------|------|
| `0000000` | 成功 |
| `B000001` | 系统错误 |
| `A000005` | 资源不存在 |

---

### 2. 视频分段

**接口**: `POST /v1/video/{video_id}/split`

**描述**: 按给定时间戳列表将视频分割为多个片段

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video_id` | Integer | 是 | 视频资产ID |

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `timestamps` | Array[Float] | 是 | 时间戳列表（秒） |

**请求示例**:

```json
{
  "timestamps": [3.0, 6.0, 9.0]
}
```

**响应示例**:

```json
{
  "code": "0000000",
  "message": "success",
  "data": {
    "video_id": 1,
    "duration": 10.5,
    "segments": [
      {
        "index": 0,
        "start": 0.0,
        "end": 3.0,
        "file": "/path/to/1_segment_000.mp4"
      },
      {
        "index": 1,
        "start": 3.0,
        "end": 6.0,
        "file": "/path/to/1_segment_001.mp4"
      },
      {
        "index": 2,
        "start": 6.0,
        "end": 9.0,
        "file": "/path/to/1_segment_002.mp4"
      },
      {
        "index": 3,
        "start": 9.0,
        "end": 10.5,
        "file": "/path/to/1_segment_003.mp4"
      }
    ],
    "total_segments": 4
  }
}
```

**错误码**:

| 错误码 | 说明 |
|--------|------|
| `0000000` | 成功 |
| `B000001` | 系统错误 |
| `A000005` | 资源不存在 |
| `A000002` | 参数错误（时间戳超出视频时长） |

---

## 音视频合成接口

### 3. 音频替换

**接口**: `POST /v1/merge/audio-replace`

**描述**: 将视频中的原音频替换为新的音频文件

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video_id` | Integer | 是 | 视频资产ID |
| `audio_id` | Integer | 是 | 新音频资产ID |

**请求示例**:

```json
{
  "video_id": 1,
  "audio_id": 2
}
```

**响应示例**:

```json
{
  "code": "0000000",
  "message": "success",
  "data": {
    "task_id": "merge_1234567890abcdef",
    "video_id": 1,
    "audio_id": 2,
    "status": "queued"
  }
}
```

**错误码**:

| 错误码 | 说明 |
|--------|------|
| `0000000` | 成功 |
| `B000001` | 系统错误 |
| `A000005` | 资源不存在 |

---

### 4. 添加背景音乐

**接口**: `POST /v1/merge/bgm`

**描述**: 为视频添加背景音乐，同时保留原音频

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video_id` | Integer | 是 | 视频资产ID |
| `bgm_id` | Integer | 是 | BGM音频资产ID |
| `bgm_volume` | Float | 否 | BGM音量（0-1），默认0.3 |
| `original_volume` | Float | 否 | 原音频音量（0-1），默认1.0 |

**请求示例**:

```json
{
  "video_id": 1,
  "bgm_id": 3,
  "bgm_volume": 0.3,
  "original_volume": 1.0
}
```

**响应示例**:

```json
{
  "code": "0000000",
  "message": "success",
  "data": {
    "task_id": "merge_1234567890abcdef",
    "video_id": 1,
    "bgm_id": 3,
    "status": "queued"
  }
}
```

**错误码**:

| 错误码 | 说明 |
|--------|------|
| `0000000` | 成功 |
| `B000001` | 系统错误 |
| `A000005` | 资源不存在 |

---

### 5. 多音轨混合

**接口**: `POST /v1/merge/mix`

**描述**: 将多个音频轨道混合后合成到视频

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `video_id` | Integer | 是 | 视频资产ID |
| `audio_ids` | Array[Integer] | 是 | 音频资产ID列表 |
| `volumes` | Array[Float] | 否 | 各音频音量列表（0-1） |

**请求示例**:

```json
{
  "video_id": 1,
  "audio_ids": [2, 3],
  "volumes": [0.7, 0.3]
}
```

**响应示例**:

```json
{
  "code": "0000000",
  "message": "success",
  "data": {
    "task_id": "merge_1234567890abcdef",
    "video_id": 1,
    "audio_ids": [2, 3],
    "status": "queued"
  }
}
```

**错误码**:

| 错误码 | 说明 |
|--------|------|
| `0000000` | 成功 |
| `B000001` | 系统错误 |
| `A000005` | 资源不存在 |

---

### 6. 查询合成任务状态

**接口**: `GET /v1/merge/tasks/{task_id}`

**描述**: 查询音视频合成任务状态

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | String | 是 | 任务ID |

**响应示例**:

```json
{
  "code": "0000000",
  "message": "success",
  "data": {
    "task_id": "merge_1234567890abcdef",
    "task_type": "audio_replace",
    "video_id": 1,
    "status": "completed",
    "result": {
      "output_path": "/path/to/output.mp4"
    },
    "error_message": null,
    "created_at": "2026-05-25T10:00:00",
    "updated_at": "2026-05-25T10:01:00"
  }
}
```

**状态说明**:

| 状态 | 说明 |
|------|------|
| `queued` | 排队中 |
| `processing` | 处理中 |
| `completed` | 已完成 |
| `failed` | 失败 |
| `cancelled` | 已取消 |

**错误码**:

| 错误码 | 说明 |
|--------|------|
| `0000000` | 成功 |
| `B000001` | 系统错误 |
| `A000005` | 资源不存在 |

---

### 7. 取消合成任务

**接口**: `POST /v1/merge/tasks/{task_id}/cancel`

**描述**: 取消正在进行的合成任务

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | String | 是 | 任务ID |

**响应示例**:

```json
{
  "code": "0000000",
  "message": "success",
  "data": {
    "task_id": "merge_1234567890abcdef",
    "status": "cancelled",
    "message": "任务已取消"
  }
}
```

**错误码**:

| 错误码 | 说明 |
|--------|------|
| `0000000` | 成功 |
| `B000001` | 系统错误 |
| `A000005` | 资源不存在 |
| `A000002` | 参数错误（任务状态不允许取消） |

---

## 使用示例

### 获取视频时长

```bash
curl -X GET "http://localhost:8000/v1/video/1/info" \
  -H "Authorization: Bearer <token>"
```

### 按时间戳分段视频

```bash
curl -X POST "http://localhost:8000/v1/video/1/split" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"timestamps": [3.0, 6.0, 9.0]}'
```

### 替换视频音频

```bash
curl -X POST "http://localhost:8000/v1/merge/audio-replace" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"video_id": 1, "audio_id": 2}'
```

### 添加背景音乐

```bash
curl -X POST "http://localhost:8000/v1/merge/bgm" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"video_id": 1, "bgm_id": 3, "bgm_volume": 0.3, "original_volume": 1.0}'
```

### 混合多音轨

```bash
curl -X POST "http://localhost:8000/v1/merge/mix" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"video_id": 1, "audio_ids": [2, 3], "volumes": [0.7, 0.3]}'
```

### 查询任务状态

```bash
curl -X GET "http://localhost:8000/v1/merge/tasks/merge_1234567890abcdef" \
  -H "Authorization: Bearer <token>"
```

### 取消任务

```bash
curl -X POST "http://localhost:8000/v1/merge/tasks/merge_1234567890abcdef/cancel" \
  -H "Authorization: Bearer <token>"
```
