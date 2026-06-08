# VidMuse 对话式工作流 — 全流程 Bug 排查报告

> 生成日期：2026-06-08
> 排查范围：前端对话 → 项目创建 → 剧本/图片/视频生成 → 修改/重生成全链路

---

## 目录

- [测试 1：上传商品/素材/参考图 → 解析内容是否传入剧本生成](#测试-1)
- [测试 2：剧本生成完成后 → 修改剧本指令](#测试-2)
- [测试 3：图片生成完成后 → 修改图片指令](#测试-3)
- [测试 4：图片生成完成后 → 修改剧本指令](#测试-4)
- [测试 5：视频生成完成后 → 换 BGM 指令](#测试-5)
- [测试 6：视频生成完成后 → 换旁白指令](#测试-6)
- [测试 7：视频生成完成后 → 换剧本指令](#测试-7)
- [测试 8：视频生成完成后 → 换分镜图指令](#测试-8)
- [通用问题](#通用问题)
- [汇总表](#汇总表)

---

<a id="测试-1"></a>
## 测试 1：上传商品 / 素材库资产 / 本地参考图 → 解析内容是否传入剧本生成

### BUG 1.1 — 素材库资产 `ai_features` 提取路径不一致导致部分内容丢失

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/controller/generation.py:103-104`
- `backend/v1/app/script/service/script_generation_service.py:483-503`
- `backend/v1/app/generate/service/chat/material_resolver.py:11-52`

**描述：**
素材库资产的 `ai_features` 在两个独立路径中被读取，但提取逻辑不同：

| 数据格式 | MaterialResolver（项目创建时） | `_build_material_reference`（剧本生成时） |
|----------|-------------------------------|------------------------------------------|
| `prompt_summary.reference_text` | ✅ 读取 | ❌ 不读取 |
| `prompt_summary.strategy_points` | ❌ | ✅ |
| `prompt_summary.selling_points` | ❌ | ✅ |
| `prompt_summary.visual_points` | ❌ | ✅ |
| `prompt_summary.audience` | ❌ | ✅ |
| `prompt_summary.scenarios` | ❌ | ✅ |
| `product_data.basic_info` | ✅ | ❌ |
| `product_data.selling_points` | ✅ | ❌ |
| `product_data.tags` | ✅ | ❌ |
| `product_data.keywords` | ✅ | ❌ |

项目创建时 `MaterialResolver` 计算的 `material_prompt_text` 被完全丢弃（只用了 `selected_asset_ids`）。剧本生成时 `_build_material_reference` 重新读取 `ai_features`，但如果资产的 `ai_features` 只包含 `product_data` 格式（没有 `prompt_summary`），则会被 `if not prompt_summary: continue` 跳过。

**复现步骤：**
1. 上传一个素材，其 `ai_features` 仅包含 `product_data` 格式（无 `prompt_summary`）
2. 在聊天中选择该素材创建项目
3. 触发剧本生成
4. 检查 LLM 收到的 prompt，发现该素材的解析内容未包含在内

**预期行为：** 无论 `ai_features` 使用哪种格式，素材解析内容都应传入剧本生成。

**修复建议：**
在 `_build_material_reference` 中增加对 `product_data` 格式的兼容处理，或统一两条路径的提取逻辑。

```python
# script_generation_service.py _build_material_reference 方法中
for asset in result.scalars().all():
    ai_features = asset.ai_features or {}
    if not isinstance(ai_features, dict):
        continue
    prompt_summary = ai_features.get("prompt_summary", {}) or {}
    product_data = ai_features.get("product_data", {}) or {}
    if not prompt_summary and not product_data:
        continue
    materials.append({
        "title": asset.title or f"Asset {asset.id}",
        "prompt_summary": prompt_summary,
        "product_data": product_data,  # 新增
    })
```

---

### BUG 1.2 — 聊天中追加选择的素材不会被后续剧本重生成使用

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/controller/generation.py:623-627`
- `backend/v1/app/generate/service/chat/chat_service.py:181-214`

**描述：**
当用户在已有项目的聊天中发送消息并选择素材时，`selected_assets` 被存入 `metadata["selected_assets"]`，但 `chat_service.handle_message()` 和 `handle_message_stream()` **从未读取**该字段。素材解析只在项目创建时通过 `MaterialResolver` 执行一次。

**复现步骤：**
1. 创建项目（不选素材）
2. 剧本生成完成
3. 在聊天中选择素材库资产，发送"重新生成剧本"
4. 剧本重生成时不会包含所选素材的解析内容

**预期行为：** 聊天中选择的素材应能影响后续剧本生成。

**修复建议：**
在 `chat_service._generate_script_from_chat()` 中读取 `metadata["selected_assets"]`，调用 `MaterialResolver` 解析后传入 `generate_script()`。

---

<a id="测试-2"></a>
## 测试 2：剧本生成完成后 → 传入修改剧本指令

### BUG 2.1 — `revise_script` 不会自动失效下游阶段

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/script/service/script_generation_service.py:221`

**描述：**
`generate_script()` 和 `revise_script()` 只调用 `mark_project_stage_review(project, "script")`，**不调用** `invalidate_project_from()`。通过 chat_service 的 `_handle_edit_frame` 路径时会正确处理失效，但通过直接 API 调用 `revise_script` 时，旧的图片和视频 URL 不会被清理，工作流状态不会回退。

**复现步骤：**
1. 完成视频生成，项目处于 `completed` 阶段
2. 通过非 chat 路径调用 `revise_script`（如直接 API）
3. 剧本更新但 `workflow_stage` 仍为 `completed`
4. 旧图片和视频 URL 仍然保留

**预期行为：** 剧本变更后应自动将工作流回退到 `script` 阶段，清除下游产物。

**修复建议：**
在 `revise_script` 末尾增加失效逻辑：

```python
from backend.v1.app.generate.service.workflow.state import generation_workflow_service
generation_workflow_service.invalidate_from(project, "script")
```

---

### BUG 2.2 — `generate_script` 跳过已有帧时不会更新剧本版本

**严重度：** 🟢 低

**位置：**
- `backend/v1/app/script/service/script_generation_service.py:81-88`

**描述：**
当 `force=False` 且帧数据完整时，`generate_script` 直接返回已有帧，不创建新的 Script 版本。这意味着如果用户期望"重新生成"但实际上帧是完整的，不会有任何变化。

**复现步骤：**
1. 项目已有完整帧数据（status 非 3，description 和 prompt 都存在）
2. 调用 `generate_script(db, project_id, force=False)`
3. 返回的帧是旧的，没有重新生成

**预期行为：** 这是设计行为（避免重复生成），但在用户期望重新生成时可能造成困惑。建议在 chat_service 路径中始终传 `force=True`。

---

<a id="测试-3"></a>
## 测试 3：图片生成完成后 → 传入修改图片指令

### BUG 3.1 — 单帧图片重生成后不会自动推进到视频阶段

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/service/chat/chat_service.py:884-899`
- `backend/v1/app/generate/tasks/video_tasks.py:894-950`

**描述：**
用户通过聊天说"把第2张图改成..." → LLM 识别为 `REGENERATE_FRAME_IMAGE` → 确认后 → `_submit_frame_image_regeneration_tasks()` → Celery 任务 `generate_frame_image_task`。

该任务执行后：
- ✅ 重新生成该帧图片
- ✅ 设置 `frame.dirty = 1`
- ✅ 更新 `frame.image_url`
- ❌ 不会自动触发视频重生成
- ❌ 不会写入 Conversation 消息通知前端

用户需要手动再说一次"生成视频"或在 FrameGrid 中操作。

**复现步骤：**
1. 完成图片生成，项目处于 `image/awaiting_review`
2. 在聊天中说"把第3张图的背景换成蓝色"
3. 确认重生成
4. 等待图片重生成完成
5. 项目停留在 `image/awaiting_review`，不会自动进入视频生成

**预期行为：** 单帧图片重生成完成后，应自动提示用户确认并推进到视频阶段，或直接触发视频重生成。

**修复建议：**
在 `generate_frame_image_task` 完成后，检查项目所有帧是否都已有图片，如果是，自动将项目标记为 `image/awaiting_review` 并写入一条 Conversation 消息提示用户可以推进到视频阶段。

---

### BUG 3.2 — 单帧图片重生成结果不推送到前端对话框

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/tasks/video_tasks.py:894-950`

**描述：**
`generate_frame_image_task` 完成后只更新数据库中的 `frame.image_url` 和 `frame.status`，**不写入 Conversation 消息**。前端只能通过轮询 `useProjectPolling`（每 3 秒）获取更新，聊天框中不会显示"图片已更新"的消息。

**复现步骤：**
1. 通过聊天触发单帧图片重生成
2. 等待任务完成
3. 聊天框中没有任何新消息
4. 需要切换到分镜面板才能看到新图片

**预期行为：** 图片重生成完成后应写入一条 Conversation 消息，包含新图片的 image_grid block。

**修复建议：**
在 `generate_frame_image_task` 成功后，创建一条 assistant Conversation 消息：

```python
db.add(Conversation(
    project_id=project_id,
    role="assistant",
    content=f"第{frame.sequence}个分镜的图片已重新生成。",
    message_type="stage_card",
    stage="image",
    blocks=[{"type": "image_grid", "frames": [{"id": frame.id, "image_url": frame.image_url, "sequence": frame.sequence}]}],
    action_type="REGENERATE_FRAME_IMAGE",
    task_id=task_id,
))
```

---

<a id="测试-4"></a>
## 测试 4：图片生成完成后 → 传入修改剧本指令

### ✅ 功能正常

当 LLM 识别为 `EDIT_FRAME` 且修改了 `description` / `image_prompt`：

```python
# chat_service.py:750-767
generation_workflow_service.invalidate_from(project, "image")
project_workflow_state.mark_project_stage_review(project, "script", project.last_task_id)
task_result = await video_generation_service.submit_generation_task(
    db, project.id, require_ready_images=False, trigger_source="chat_semantic_edit",
)
```

会正确回退工作流状态，重新触发完整的图片 + 视频生成流程。

---

<a id="测试-5"></a>
## 测试 5：视频生成完成后 → 传入换 BGM 指令

### BUG 5.1 — 选中的 BGM ID 未持久化，`exclude_ids` 永远为空

**严重度：** 🔴 严重

**位置：**
- `backend/v1/app/generate/service/chat/chat_service.py:789-790`

**描述：**
```python
exclude_ids = []  # 永远为空列表！
bgm_id = bgm_selector_service.select_bgm(db, script_content, exclude_ids=exclude_ids)
```

选中的 `bgm_id` 没有存入数据库（没有存到 project、script 或任何地方）。`exclude_ids` 永远为空列表，导致下次换 BGM 时 `select_bgm` 可能选到同一首音乐。

**复现步骤：**
1. 完成视频生成
2. 说"换个BGM" → 视频重生成完成
3. 再说"换个BGM" → 可能选到同一首

**预期行为：** 每次换 BGM 应排除当前正在使用的 BGM，确保选到不同的。

**修复建议：**

方案 A：将 BGM ID 存入 project 的 `ai_params` 或新增字段：
```python
# _handle_change_bgm 中
bgm_id = bgm_selector_service.select_bgm(db, script_content, exclude_ids=exclude_ids)
# 持久化到 project
project_ai_params = dict(project.ai_params or {})
project_ai_params["current_bgm_id"] = bgm_id
project.ai_params = project_ai_params
```

方案 B：将 BGM ID 存入最新的 Script 记录。

---

### BUG 5.2 — 换 BGM 后新视频不会推送到前端对话框

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/tasks/video_tasks.py:740-760`（视频生成完成后写入 Conversation 的逻辑）

**描述：**
视频重生成完成后，`generate_video_task` 会写入一条 Conversation 消息（`stage_card` 类型），前端通过轮询可以获取新视频 URL。但聊天框中的消息是异步写入的，用户发送"换BGM"后看到的是 progress_card，新视频生成完成后的 stage_card 消息需要等轮询刷新才能看到。

**复现步骤：**
1. 视频完成后说"换个BGM"
2. 收到"已更换背景音乐，正在重新生成视频"的 progress_card
3. 等待视频重生成完成
4. 聊天框中不会自动出现新视频消息，需要滚动或切换项目再切回

**预期行为：** 视频重生成完成后，新视频 card 应自动出现在聊天框底部。

**修复建议：**
确保 `useChat` 的 `onMessageHandled` 回调触发 `refetch()`，并在 Conversation 加载时将新消息追加到聊天列表。当前实现中 `useProjectPolling` 的 `refetch()` 会更新帧和视频 URL，但不会自动刷新聊天消息列表。需要在视频任务完成后触发 `conversationVersion` 递增。

---

<a id="测试-6"></a>
## 测试 6：视频生成完成后 → 传入换旁白指令

### BUG 6.1 — 纯 narration 修改不会自动触发 TTS / 视频重生成

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/service/chat/chat_service.py:718-767`

**描述：**
当用户只修改 `narration`（不改 `description` / `image_prompt`）时：
- `affects_image` = False（因为 `image_affecting_fields = {"description", "image_prompt"}`）
- 不进入 `should_regen_image` 分支
- 只执行 `generation_workflow_service.invalidate_from(project, "video")`
- **没有提交任何重生成任务**

用户需要手动再说"生成视频"来触发重生成。

对比：如果 LLM 识别为 `REGENERATE_TTS`，则 `_submit_project_tts_regeneration_task()` 会正确提交 TTS 重生成任务。但 LLM 也可能识别为 `EDIT_FRAME`（修改 narration 字段），此时就不会自动触发。

**复现步骤：**
1. 视频完成后说"把第2个分镜的旁白改成'大家好'"
2. LLM 识别为 EDIT_FRAME，修改 narration 字段
3. 工作流回退到 video/confirmed（或 image/confirmed）
4. 但没有提交任何重生成任务
5. 用户需要再说"生成视频"

**预期行为：** narration 修改后应自动检测 TTS dirty，提交 TTS 重生成或完整视频重生成任务。

**修复建议：**
在 `_handle_edit_frame` 中，当 `affects_narration` 为 True 且当前在 video/completed 阶段时，除了标记 `tts_dirty` 外，还应提交重生成任务：

```python
if affects_narration and project.workflow_stage in ("video", "completed"):
    ai_params = dict(frame.ai_params or {})
    ai_params["tts_dirty"] = True
    frame.ai_params = ai_params
    # 新增：自动提交视频重生成
    should_regen_video = True

# 在循环外
if should_regen_video:
    generation_workflow_service.invalidate_from(project, "video")
    await db.flush()
    task_result = await video_generation_service.submit_generation_task(
        db, project.id, trigger_source="chat_narration_edit",
    )
    blocks.append(build_progress_block("video", "running", task_result.get("task_id"), "旁白已修改，正在重新生成视频。"))
```

---

<a id="测试-7"></a>
## 测试 7：视频生成完成后 → 传入换剧本指令

### ✅ 核心功能正常

LLM 识别为 `REGENERATE_PROJECT_ALL` 或 `REGENERATE_IMAGES_AND_VIDEO` → 确认后 → `_submit_project_regeneration()`：

```python
# chat_service.py:964-980
await script_generation_service.generate_script(db, project_id, force=True)
for frame in frames:
    frame.image_url = None
    frame.video_url = None
    frame.status = 0
    frame.dirty = 1
task_result = await video_generation_service.submit_generation_task(
    db, project_id, require_ready_images=False, trigger_source="chat_regenerate_project_all",
)
```

会重新生成剧本 → 图片 → 视频，完整链路。

### BUG 7.1 — 旧图片 / 视频文件未从云存储中删除

**严重度：** 🟢 低

**位置：**
- `backend/v1/app/generate/service/chat/chat_service.py:968-971`

**描述：**
重生成时只清空了数据库中的 URL（`frame.image_url = None`, `frame.video_url = None`），但旧文件仍然保存在云存储中，造成存储浪费。

**复现步骤：**
1. 完成视频生成（有 5 个分镜图片 + 1 个视频）
2. 说"重新生成整个剧本"
3. 确认后新图片和视频生成完成
4. 云存储中旧的 5 张图片和 1 个视频文件仍然存在

**预期行为：** 重生成前应删除旧的云存储文件。

**修复建议：**
在清空 URL 前，先调用存储服务删除旧文件：

```python
for frame in frames:
    if frame.image_url:
        await storage_service.delete(frame.image_url)
    if frame.video_url:
        await storage_service.delete(frame.video_url)
    frame.image_url = None
    frame.video_url = None
```

---

<a id="测试-8"></a>
## 测试 8：视频生成完成后 → 传入换分镜图指令

### BUG 8.1 — 同 BUG 3.1：只重生成单帧图片，不自动推进到视频

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/service/chat/chat_service.py:884-899`

**描述：**
与测试 3 的 BUG 3.1 相同。用户说"把第3个分镜图换成..." → 确认后 → `_submit_frame_image_regeneration_tasks()` → Celery 任务 `generate_frame_image_task`。

完成后只更新单帧图片，不自动触发视频重生成，不在对话框中显示新图片。

**复现步骤：**
1. 视频完成后说"把第3个分镜的图片换成海边场景"
2. 确认重生成
3. 等待图片重生成完成
4. 项目停留在当前阶段，视频不会自动重生成
5. 聊天框中没有新图片的反馈

**预期行为：** 分镜图重生成完成后，应自动提示用户可以推进到视频阶段。

---

<a id="通用问题"></a>
## 通用问题

### BUG A — `image_workflow.py` 缺少导入，同步路径运行时崩溃

**严重度：** 🔴 严重

**位置：**
- `backend/v1/app/generate/service/stages/image_workflow.py`

**描述：**
同步路径 `generate_images()` 方法引用了 `Conversation` 但未导入。`_extract_product_images()` 方法引用了 `json.loads` 但未导入。如果这两个方法被调用，会在运行时抛出 `NameError`。

**复现步骤：**
1. 调用 `image_workflow_service.generate_images()` 同步路径
2. 在创建 Conversation 消息时抛出 `NameError: name 'Conversation' is not defined`

**修复建议：**
在文件顶部添加缺失的导入：

```python
import json
from backend.v1.app.models.conversation import Conversation
```

---

### BUG B — `handle_message` 和 `handle_message_stream` 逻辑重复

**严重度：** 🔴 严重（维护风险）

**位置：**
- `backend/v1/app/generate/service/chat/chat_service.py:221-332`（handle_message）
- `backend/v1/app/generate/service/chat/chat_service.py:456-499`（handle_message_stream）

**描述：**
两个方法包含几乎相同的 action 分发逻辑（15+ 个 action 分支）。新增 action 必须在两处同步修改，容易遗漏导致行为不一致。

**修复建议：**
提取公共的 action 执行逻辑到一个私有方法：

```python
async def _execute_action(self, db, project, project_id, plan, metadata=None):
    """统一的 action 执行逻辑，供 handle_message 和 handle_message_stream 共用。"""
    action = plan["action"]
    task_result = None
    updated_frames = []
    blocks = []
    pending_action = None

    if action == "GENERATE_SCRIPT":
        task_result, blocks = await self._generate_script_from_chat(db, project, project_id, metadata=metadata)
    elif action == "CONFIRM_AND_ADVANCE":
        task_result, blocks = await self._handle_confirm_and_advance(db, project, project_id)
    # ... 其他 action
    return task_result, updated_frames, blocks, pending_action
```

---

### BUG C — 前端 `updated_frames` 未被 FrameGrid 使用

**严重度：** 🟡 中等

**位置：**
- `frontend/src/hooks/useChat.js:273`
- `frontend/src/components/Keyframes/FrameGrid.jsx`

**描述：**
SSE `done` 事件中的 `updated_frames` 存入了消息 metadata，但 `FrameGrid` 组件不读取这个字段，完全依赖 `useProjectPolling` 轮询（每 3 秒）。帧更新有最多 3 秒延迟。

**修复建议：**
在 `useChat` 的 `onDone` 回调中，通过 `onMessageHandled` 传递 `updated_frames`，让 FrameGrid 可以立即更新对应帧的数据，而不必等待轮询。

---

### BUG D — `useProjectPolling` 在 `awaiting_review` 时持续轮询不停止

**严重度：** 🟡 中等

**位置：**
- `frontend/src/hooks/useProjectPolling.js:57-61`

**描述：**
当 `stage_status === 'awaiting_review'` 时，`isProjectTerminal()` 返回 False（因为 `awaiting_review` 不是终态），轮询继续。如果用户不操作（不确认也不发消息），轮询会**永远持续**（每 3 秒一次），浪费网络和服务器资源。

```javascript
const workflowRunning = data.stage_status === 'running'
const awaitingWorkflowReview = data.stage_status === 'awaiting_review'
if (!workflowRunning && !awaitingWorkflowReview && isProjectTerminal(data)) {
    clearInterval(intervalRef.current)
}
```

**修复建议：**
增加最大轮询次数或超时机制：

```javascript
// 轮询超过 5 分钟（100 次）且状态未变化时停止
if (pollCount > 100 && !workflowRunning && !awaitingWorkflowReview) {
    clearInterval(intervalRef.current)
}
```

或改为事件驱动：前端订阅 WebSocket / SSE 通知，而不是轮询。

---

### BUG E — 视频任务多线程写 ORM 对象存在数据竞争风险

**严重度：** 🟡 中等

**位置：**
- `backend/v1/app/generate/tasks/video_tasks.py:167-178`

**描述：**
`_generate_frame_videos_parallel` 使用 `ThreadPoolExecutor`（最大 5 个线程）并行生成帧视频。每个线程调用 `_persist_frame_video_segment` 直接修改 `frame.video_url` 和 `frame.dirty` ORM 对象属性。

虽然实际的 `db.commit()` 在主线程执行，但 ORM 对象的属性赋值不是线程安全的。在高并发场景下可能导致数据不一致。

**修复建议：**
改为在线程中只返回结果（URL 等），在主线程中统一更新 ORM 对象：

```python
# 线程中只返回结果
result = {"frame_id": frame.id, "video_url": uploaded_url}

# 主线程中统一更新
for result in results:
    frame = frame_map[result["frame_id"]]
    frame.video_url = result["video_url"]
    frame.dirty = 0
```

---

### BUG F — MainLayout 所有组件始终挂载，不可见组件仍在轮询

**严重度：** 🟡 中等

**位置：**
- `frontend/src/components/Layout/MainLayout.jsx`

**描述：**
使用 `style={{ display: 'block'/'none' }}` 控制视图切换，所有组件（FrameGrid、MediaGrid、ProductManager 等）始终挂载。即使组件不可见，其 `useEffect` 和轮询逻辑仍在运行，造成不必要的 API 调用。

**修复建议：**
改为条件渲染：

```jsx
{activeView === 'keyframes' && <FrameGrid />}
{activeView === 'media' && <MediaGrid />}
{activeView === 'products' && <ProductManager />}
```

或使用 `useMemo` + visibility state 控制轮询的启停。

---

### BUG G — `scriptMode` 状态在 FrameGrid 和 WorkbenchView 中重复定义

**严重度：** 🟢 低

**位置：**
- `frontend/src/components/Keyframes/FrameGrid.jsx:252`
- `frontend/src/components/Workbench/WorkbenchView.jsx`

**描述：**
`scriptMode`（创作模式：自主创作/自动选择/爆款融合）在 FrameGrid 和 WorkbenchView 中各自独立管理。用户在一个地方切换模式后，另一个地方不会同步，可能导致不一致。

**修复建议：**
将 `scriptMode` 提升到全局 store（如 `appStore`）中，两个组件共用同一状态。

---

### BUG H — `analyze_chat_reference` 返回的 UUID 不持久化

**严重度：** 🟢 低

**位置：**
- `backend/v1/app/generate/controller/generation.py:746`

**描述：**
`analyze_chat_reference` 端点返回的 `id` 是 `uuid.uuid4().hex`，没有存入数据库。如果前端后续需要用这个 ID 引用已分析的图片，服务端无法查找。

**修复建议：**
要么将分析结果存入 asset 表并返回真实 ID，要么前端只使用返回的 URL 而不依赖 ID。

---

<a id="汇总表"></a>
## 汇总表

| # | 严重度 | 测试 | 问题 | 影响 |
|---|--------|------|------|------|
| 1.1 | 🟡中等 | 测试1 | 素材库 `ai_features` 提取路径不一致 | `product_data` 格式素材内容丢失 |
| 1.2 | 🟡中等 | 测试1 | 聊天追加素材在后续对话中被忽略 | 项目创建后追加素材无效 |
| 2.1 | 🟡中等 | 测试2 | `revise_script` 不失效下游阶段 | 非 chat 路径修改剧本不触发重生成 |
| 2.2 | 🟢低 | 测试2 | `generate_script` 跳过完整帧 | force=False 时不重新生成 |
| 3.1 | 🟡中等 | 测试3 | 单帧图片重生成不推进到视频 | 用户需手动触发视频生成 |
| 3.2 | 🟡中等 | 测试3 | 图片重生成结果不推送对话框 | 聊天框无反馈 |
| 5.1 | 🔴严重 | 测试5 | BGM ID 未持久化，exclude_ids 永远为空 | 换 BGM 可能选到同一首 |
| 5.2 | 🟡中等 | 测试5 | 新视频不推送对话框 | 聊天框无实时反馈 |
| 6.1 | 🟡中等 | 测试6 | 纯 narration 修改不自动触发重生成 | 用户需手动触发 |
| 7.1 | 🟢低 | 测试7 | 旧文件未从云存储删除 | 存储浪费 |
| 8.1 | 🟡中等 | 测试8 | 同 BUG 3.1 | 同 3.1 |
| A | 🔴严重 | 通用 | `image_workflow.py` 缺少导入 | 同步路径运行时崩溃 |
| B | 🔴严重 | 通用 | action 分发逻辑重复 | 新 action 易遗漏 |
| C | 🟡中等 | 通用 | `updated_frames` 未被 FrameGrid 使用 | 帧更新有 3 秒延迟 |
| D | 🟡中等 | 通用 | `awaiting_review` 时持续轮询 | 资源浪费 |
| E | 🟡中等 | 通用 | 多线程写 ORM 对象 | 潜在数据不一致 |
| F | 🟡中等 | 通用 | 所有组件始终挂载 | 不必要的 API 调用 |
| G | 🟢低 | 通用 | `scriptMode` 状态重复定义 | 模式不同步 |
| H | 🟢低 | 通用 | 分析结果 UUID 不持久化 | 无法通过 ID 查找 |

**统计：** 🔴 严重 3 个 | 🟡 中等 12 个 | 🟢 低 4 个

**优先修复建议：**
1. **BUG A**（缺少导入）— 一行代码修复，立即处理
2. **BUG 5.1**（BGM ID 未持久化）— 影响用户体验，尽快修复
3. **BUG B**（逻辑重复）— 重构消除重复，降低后续维护风险
4. **BUG 3.1 / 8.1**（单帧重生成不推进）— 改善用户体验
5. **BUG 6.1**（narration 修改不自动触发）— 改善用户体验
