# 素材管理 API 接口文档

## 接口概览

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| POST | `/api/v1/materials` | 上传素材 | 登录用户 |
| GET | `/api/v1/materials` | 查询素材列表 | 登录用户 |
| PUT | `/api/v1/materials/{material_id}` | 修改素材信息 | 登录用户/管理员 |
| DELETE | `/api/v1/materials/{material_id}` | 删除素材 | 上传者/管理员 |

## 公共返回格式

所有接口返回统一格式：
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```
- `code`: 错误码，0表示成功，非0表示失败
- `message`: 提示信息
- `data`: 返回数据

## 接口详情

### 1. 上传素材接口
**接口地址**：`POST /api/v1/materials`

**功能描述**：上传素材到素材库，支持图片、视频、音频类型。上传后系统会自动进行AI内容分析，生成描述和标签。

**请求参数**：
| 参数名 | 类型 | 是否必填 | 描述 |
|--------|------|----------|------|
| file | File | 是 | 素材文件 |
| type | int | 是 | 素材类型：1-图片 2-视频 3-音频 |
| title | string | 是 | 素材标题 |
| tags | string | 否 | 标签，多个标签用逗号分隔 |
| source_type | int | 否 | 来源类型：1-上传 2-AI生成 3-爬取 4-购买，默认1 |

**请求示例**：
```http
POST /api/v1/materials
Content-Type: multipart/form-data

file: [二进制文件]
type: 1
title: 产品宣传图
tags: 产品,宣传,电商
source_type: 1
```

**返回示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1001,
    "type": 1,
    "title": "产品宣传图",
    "url": "https://minio.example.com/materials/image/宣/传/产品宣传图.jpg",
    "file_size": 1024000,
    "duration": null,
    "format": "jpg",
    "source_type": 1,
    "ai_features": {
      "description": "这是一张产品宣传图，展示了新款智能手机的外观设计，背景为渐变色，突出产品的科技感。",
      "tags": ["产品", "宣传", "电商", "手机", "科技"]
    },
    "created_at": "2026-05-23T18:00:00"
  }
}
```

### 2. 查询素材列表接口
**接口地址**：`GET /api/v1/materials`

**功能描述**：多维度检索素材列表，支持分页、按类型筛选、关键词搜索。

**请求参数**：
| 参数名 | 类型 | 是否必填 | 描述 |
|--------|------|----------|------|
| type | int | 否 | 素材类型筛选：1-图片 2-视频 3-音频 |
| keyword | string | 否 | 关键词搜索，匹配素材标题 |
| uploader_id | int | 否 | 上传者ID筛选 |
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页数量，默认20，最大100 |

**请求示例**：
```http
GET /api/v1/materials?type=1&keyword=产品&page=1&page_size=10
```

**返回示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 100,
    "page": 1,
    "page_size": 10,
    "list": [
      {
        "id": 1001,
        "type": 1,
        "title": "产品宣传图",
        "url": "https://minio.example.com/materials/image/宣/传/产品宣传图.jpg",
        "duration": null,
        "format": "jpg",
        "source_type": 1
      },
      {
        "id": 1002,
        "type": 1,
        "title": "产品详情图",
        "url": "https://minio.example.com/materials/image/详/情/产品详情图.jpg",
        "duration": null,
        "format": "png",
        "source_type": 1
      }
    ]
  }
}
```

### 3. 修改素材信息接口
**接口地址**：`PUT /api/v1/materials/{material_id}`

**功能描述**：修改素材的基本信息，仅支持修改标题和标签。

**路径参数**：
| 参数名 | 类型 | 是否必填 | 描述 |
|--------|------|----------|------|
| material_id | int | 是 | 素材ID |

**请求参数**：
| 参数名 | 类型 | 是否必填 | 描述 |
|--------|------|----------|------|
| title | string | 否 | 新的素材标题 |
| tags | string | 否 | 新的标签列表，多个标签用逗号分隔（传入则完全替换原有标签） |

**请求示例**：
```http
PUT /api/v1/materials/1001
Content-Type: application/x-www-form-urlencoded

title: 新款手机宣传图
tags: 手机,新款,2026,科技,电商
```

**返回示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1001,
    "type": 1,
    "title": "新款手机宣传图",
    "url": "https://minio.example.com/materials/image/宣/传/产品宣传图.jpg",
    "file_size": 1024000,
    "duration": null,
    "format": "jpg",
    "source_type": 1,
    "ai_features": {
      "description": "这是一张产品宣传图，展示了新款智能手机的外观设计，背景为渐变色，突出产品的科技感。",
      "tags": ["手机", "新款", "2026", "科技", "电商"]
    },
    "created_at": "2026-05-23T18:00:00"
  }
}
```

### 4. 删除素材接口
**接口地址**：`DELETE /api/v1/materials/{material_id}`

**功能描述**：删除指定素材，同时会删除对象存储中的文件。仅素材上传者或管理员可以删除。

**路径参数**：
| 参数名 | 类型 | 是否必填 | 描述 |
|--------|------|----------|------|
| material_id | int | 是 | 素材ID |

**请求示例**：
```http
DELETE /api/v1/materials/1001
```

**返回示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

## 错误码说明

| 错误码 | 描述 | 解决方案 |
|--------|------|----------|
| 10001 | 参数错误 | 检查请求参数是否符合要求 |
| 10002 | 文件大小超过限制 | 上传文件大小不能超过系统设定的最大值（默认50MB） |
| 10003 | 文件格式不允许 | 检查文件格式是否符合对应素材类型的允许格式 |
| 10004 | 素材不存在 | 检查material_id是否正确 |
| 10005 | 无权限操作 | 只有素材上传者或管理员可以修改/删除素材 |
| 20001 | 上传失败 | 服务器存储异常，请稍后重试 |
| 20002 | 删除失败 | 服务器存储异常，请稍后重试 |

## 素材类型说明

| 类型值 | 类型名称 | 允许格式 |
|--------|----------|----------|
| 1 | 图片 | jpg, jpeg, png, gif, webp |
| 2 | 视频 | mp4, avi, mov, flv, webm |
| 3 | 音频 | mp3, wav, aac, flac |

## 来源类型说明

| 类型值 | 来源描述 |
|--------|----------|
| 1 | 用户上传 |
| 2 | AI生成 |
| 3 | 网络爬取 |
| 4 | 版权购买 |