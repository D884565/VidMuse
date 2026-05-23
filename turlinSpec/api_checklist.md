# 接口验证清单

## 快速检查表

### 对象存储接口 ✅

| 接口 | 文件 | 状态 | 备注 |
|------|------|------|------|
| upload_file | minio_client.py:56 | ✅ | 上传本地文件 |
| upload_fileobj | minio_client.py:70 | ✅ | 上传文件对象 |
| get_presigned_url | minio_client.py:86 | ✅ | 获取下载URL |
| download_file | minio_client.py:97 | ✅ | 下载到本地 |
| get_object | minio_client.py:108 | ✅ | 获取内容 |
| delete_object | minio_client.py:123 | ✅ | 删除对象 |
| object_exists | minio_client.py:145 | ✅ | 检查存在 |

**TOS客户端**: 同样接口，火山引擎实现 ✅

---

### AI接口 ✅

| 接口 | 文件 | 状态 | 用途 |
|------|------|------|------|
| _chat | volcano.py:92 | ✅ | 剧本生成 |
| _stream_chat | volcano.py:138 | ✅ | 流式对话 |
| generate_video | volcano.py:173 | ✅ | 视频生成 |
| text_understanding | volcano.py:420 | ✅ | 文本理解 |
| image_understanding | volcano.py:301 | ✅ | 图片理解 |

---

### 数据库模型 ✅

| 模型 | 文件 | 状态 | 用途 |
|------|------|------|------|
| Project | project.py | ✅ | 项目主表 |
| Script | script.py | ✅ | 剧本表 |
| Material | material.py | ✅ | 素材表 |

---

## 需要实现的服务

### 1. minio_service 封装 ⚠️ 需新建

**位置**: `backend/v1/app/services/minio_service.py`

**原因**: video_tasks.py中引用但不存在

**解决方案**:
```python
from backend.store.obj.factory import get_storage_client

class MinioService:
    def __init__(self):
        self.client = get_storage_client()

    def upload_file(self, file_path, object_name):
        return self.client.upload_file(file_path, object_name)

    def get_url(self, object_name):
        return self.client.get_presigned_url(object_name)

minio_service = MinioService()
```

---

### 2. 剧本生成服务 🔧 需修改

**文件**: `backend/v1/app/generate/service/script_generation.py`

**当前**: Mock数据

**目标**: 调用 `VolcanoLLM.text_understanding()` 或 `_chat()`

**接口已就绪**: ✅

---

### 3. TTS服务 🔧 需修改

**文件**: `backend/v1/app/generate/service/tts_service.py`

**当前**: 生成静音音频

**目标**: 调用真实TTS API

**待确认**: 使用哪个TTS服务（火山引擎/Azure/其他）

---

### 4. 图片服务 🔧 需修改

**文件**: `backend/v1/app/generate/service/image_service.py`

**当前**: 生成占位PNG

**目标**: 调用图片生成API或搜索素材库

**待确认**: 图片来源方案

---

### 5. 视频合成服务 🔧 需修改

**文件**: `backend/v1/app/generate/service/video_composer.py`

**当前**: 生成空文件

**目标**: 使用moviepy/ffmpeg合成真实视频

**依赖**: 需安装moviepy

---

## 总结

**可用接口**: 12/12 ✅
**需修改服务**: 5个
**需新建文件**: 1个

**结论**: 搭档提供的接口和函数已足够支撑视频生成功能实现，可以开始开发。
