# VidMuse Workflow, Video, Task, Model, and Frontend Fix Spec

Date: 2026-05-30

## 1. Verification Summary

This document verifies the reported issues against the current repository and defines the repair plan for the items that are still true or materially true.

### Confirmed True

1. `Frame` lacks `video_url`, and `generate_frame_video_task` stores a video URL in `frame.audio_url`.
2. `_mark_project_failed()` commits inside failure handling. The current retry path avoids final failure during retry in some cases, but direct failure branches still commit before raising and can cause externally visible failed/running flips.
3. Workflow state is split between `generation_workflow.py` and `project_workflow_state.py`. The former does not sync legacy `project.status`; callers mix both APIs.
4. `generation_workflow.invalidate_from()` sets `stage_status="awaiting_review"` even after invalidation.
5. `LEGACY_STATUS_BY_STAGE_STATUS` has incorrect image/video mappings.
6. `video_composer.compose_frames()` raises on the first frame video generation failure instead of applying a placeholder fallback.
7. Frontend `useChat.sendMessage(content, files)` displays files locally but sends only `content` to the backend.
8. `ChatContainer` uses `useWorkflowProject` and `FrameGrid` uses `useProjectPolling`; when both are mounted, they duplicate `getProjectDetail()` polling.
9. `useWorkflowProject` sets `loading=true` on every recursive poll, causing repeated loading flashes.
10. `MessageBlocks.runAction()` has no local loading, error handling, or duplicate-click protection.
11. `task_service` sync methods silently return `None` when task or step rows are missing.
12. `start_step_sync()` can move a terminal task back to `running`.
13. `start_task_sync()` does not clear `finished_at`, `error_code`, or `error_message` when reusing/retrying a task.
14. `_generate_scene_video()` reads scene duration and then hard-codes `duration = 5`.
15. `auto_render` bypasses the intended review workflow by generating script then immediately submitting render.
16. `create_task()` commits immediately, so callers cannot atomically create a task with related project/conversation updates.
17. `/frames/{frame_id}/retry` resets one frame but calls `submit_generation_task()`, triggering full render flow.
18. `task_submission.py` exists but is not imported by production modules.
19. Model problems remain: missing `Frame.video_url`; missing FKs/indexes/relationships; model constraints partly diverge from expected schema.
20. Failure handlers in single-frame and export tasks are not protected with `try/except`, unlike `generate_video_task`.
21. Single-frame task failures pass `stage=None`, so project workflow status is not updated.
22. TOS uploads are not compensated if later DB or composition steps fail.
23. Frontend refresh token is sent in query parameters.
24. Axios has no timeout.
25. `FrameGrid` uses blocking `prompt()`.
26. `useProjects` has no cancellation guard.
27. No WebSocket/SSE push exists; project state is polled every 3 seconds. Realtime push is valid but is deferred to a separate spec because it needs authentication, reconnect, and deployment design.
28. `KeyframeStudio` bypasses shared axios handling with raw `fetch()`.
29. `export_video_task` only creates an `Asset` pointing at the existing video.
30. BGM generation is commented out.
31. `compose_frames()` has no final output trim to `project.target_duration`.
32. `workflow_agent` falls back to clarification for image-stage text when no frame id is resolved.

### Already Fixed or Not Fully True in Current Code

1. `generate_video_task` no longer regenerates all existing images unconditionally because `image_generation_service.generate_frame_images()` skips frames with `status == 2` and `image_url`.
2. `generate_image_task`, `generate_frame_image_task`, `generate_frame_video_task`, and `export_video_task` now call `self.retry()` when retries remain. The remaining issue is unprotected failure-state handling and missing project stage updates for frame-level tasks.
3. `_extract_reference_images` is no longer duplicated three times. It is centralized in `reference_image_utils.extract_reference_images()`. `image_workflow._extract_reference_images()` is only a wrapper.
4. `ProjectAsset` is now queried by `video_generation_service.get_project_detail()`, so bound assets should be visible.

## 2. Goals

1. Make workflow state single-source, transition-safe, and legacy-status-compatible.
2. Separate frame audio and frame video outputs at model, task, API, and frontend levels.
3. Make Celery task retry/failure behavior transactionally consistent and observable.
4. Prevent accidental expensive full-project renders for single-frame retries.
5. Remove frontend duplicate polling and unsafe/fragile request patterns.
6. Align ORM models with the intended database integrity rules.
7. Add tests that lock the corrected behavior before implementation.
8. Keep new/changed code readable for the local team with basic Chinese comments around non-obvious workflow, transaction, and fallback decisions.

## 3. Non-Goals

1. Replace Celery with another queue.
2. Fully implement advanced export editing beyond the specified first useful transcode/crop path.
3. Do not implement SSE/WebSocket in this remediation pass. Realtime push needs its own spec; this pass should only make polling less wasteful and easier to replace later.
4. Rewrite the whole frontend layout.

## 4. Backend Workflow State Spec

### Target State Model

Allowed stages:

- `created`
- `script`
- `image`
- `video`
- `completed`

Allowed stage statuses:

- `idle`
- `running`
- `awaiting_review`
- `confirmed`
- `failed`

Legacy status mapping:

```python
LEGACY_STATUS_BY_STAGE_STATUS = {
    ("created", "idle"): "draft",
    ("script", "idle"): "draft",
    ("script", "running"): "script_generating",
    ("script", "awaiting_review"): "script_ready",
    ("script", "confirmed"): "script_ready",
    ("script", "failed"): "failed",
    ("image", "idle"): "script_ready",
    ("image", "running"): "processing",
    ("image", "awaiting_review"): "review_required",
    ("image", "confirmed"): "review_required",
    ("image", "failed"): "failed",
    ("video", "idle"): "review_required",
    ("video", "running"): "rendering",
    ("video", "awaiting_review"): "review_required",
    ("video", "confirmed"): "completed",
    ("video", "failed"): "failed",
    ("completed", "confirmed"): "completed",
}
```

`("image", "idle")` intentionally remains `script_ready` only for the forward state after script confirmation, meaning "script is ready and image generation has not started." Do not use `("image", "idle")` for image invalidation. If images are invalidated, the workflow should regress to `("script", "confirmed")` and set `dirty_stage="image"` so legacy status stays `script_ready` for the right reason.

`("video", "awaiting_review")` must not map to `processing`; video generation has completed and now needs user review. Use `review_required`, or add a new explicit `video_ready` legacy status to backend constants and frontend display maps. Do not overload `processing`.

### Implementation

Modify `backend/v1/app/generate/service/project_workflow_state.py` into the only mutation API for workflow fields.

Add:

```python
NEXT_STAGE = {"script": "image", "image": "video", "video": "completed"}
REVIEWABLE_STATUSES = {"awaiting_review", "confirmed"}
VALID_TRANSITIONS = {
    ("created", "idle", "script", "running"),
    ("script", "idle", "script", "running"),
    ("script", "running", "script", "awaiting_review"),
    ("script", "awaiting_review", "script", "confirmed"),
    ("script", "confirmed", "image", "idle"),
    ("image", "idle", "image", "running"),
    ("image", "running", "image", "awaiting_review"),
    ("image", "awaiting_review", "image", "confirmed"),
    ("image", "confirmed", "video", "idle"),
    ("video", "idle", "video", "running"),
    ("video", "running", "video", "awaiting_review"),
    ("video", "awaiting_review", "video", "confirmed"),
    ("video", "confirmed", "completed", "confirmed"),
    # 合法失效回退：保留上一个已确认阶段，标记 dirty_stage 指向需要重做的阶段。
    ("image", "idle", "script", "confirmed"),
    ("image", "running", "script", "confirmed"),
    ("image", "awaiting_review", "script", "confirmed"),
    ("image", "confirmed", "script", "confirmed"),
    ("video", "idle", "image", "confirmed"),
    ("video", "running", "image", "confirmed"),
    ("video", "awaiting_review", "image", "confirmed"),
    ("video", "confirmed", "image", "confirmed"),
    ("completed", "confirmed", "video", "confirmed"),
}
```

Add helper:

```python
def set_project_workflow_state(project, stage: str, status: str, task_id: int | None = None, *, allow_regression: bool = False) -> None:
    old_stage = getattr(project, "workflow_stage", "created")
    old_status = getattr(project, "stage_status", "idle")
    if not allow_regression and (old_stage, old_status, stage, status) not in VALID_TRANSITIONS:
        if not (stage == old_stage and status in {"running", "failed"}):
            raise ValueError(f"invalid workflow transition: {old_stage}/{old_status} -> {stage}/{status}")
    project.workflow_stage = stage
    project.stage_status = status
    if task_id is not None:
        project.last_task_id = task_id
    sync_legacy_status(project)
```

Move `confirm_stage()`, `advance_stage()`, `invalidate_from()`, `mark_stage_running()`, `mark_stage_review()`, and `fail_stage()` semantics into this module, or make `generation_workflow.py` a thin compatibility wrapper that delegates to `project_workflow_state`.

`invalidate_from(project, stage)` must regress to the last still-valid confirmed stage instead of leaving the project inside the invalidated stage:

```python
if stage == "script":
    target_stage, target_status = "script", "idle"
elif stage == "image":
    target_stage, target_status = "script", "confirmed"
elif stage == "video":
    target_stage, target_status = "image", "confirmed"
else:
    raise ValueError(f"unknown workflow stage: {stage}")

set_project_workflow_state(project, target_stage, target_status)
project.dirty_stage = stage
sync_legacy_status(project)
```

Then clear confirmation timestamps from the invalidated stage forward.

`dirty_stage` cleanup:

- `mark_stage_running(project, stage, task_id)` should keep `dirty_stage` unchanged while regeneration is in progress.
- `mark_stage_review(project, stage, task_id)` should clear `dirty_stage` when `dirty_stage == stage`, because that stage now has fresh reviewable output.
- `mark_project_completed()` should clear `dirty_stage`.
- `confirm_stage()` should not clear unrelated dirty stages. For example, confirming script must not clear `dirty_stage="image"`.

### Required Call-Site Changes

Replace direct calls to `generation_workflow_service.*` in:

- `backend/v1/app/generate/controller/generation.py`
- `backend/v1/app/generate/service/chat_service.py`
- `backend/v1/app/generate/service/storyboard_service.py`
- `backend/v1/app/generate/service/image_workflow.py`
- `backend/v1/app/generate/service/video_generation.py`
- `backend/v1/app/generate/temp/video_tasks.py`

Call only `project_workflow_state.*` mutation helpers.

### Tests

Create `backend/tests/generate/test_project_workflow_state.py`:

- invalidating image sets `stage_status == "idle"` and legacy status `script_ready` or `review_required` according to chosen mapping.
- invalidating image regresses to `workflow_stage == "script"` and `stage_status == "confirmed"` with `dirty_stage == "image"`.
- invalidating video regresses to `workflow_stage == "image"` and `stage_status == "confirmed"` with `dirty_stage == "video"`.
- mark image review clears `dirty_stage == "image"` after successful regeneration.
- image awaiting review does not map to `script_ready`.
- video awaiting review maps to `review_required`, not `processing`.
- video confirmed maps to `completed`.
- illegal transition from `script/idle` directly to `video/running` raises `ValueError`, while explicit invalidation regressions listed in `VALID_TRANSITIONS` pass without `allow_regression=True`.
- compatibility wrapper calls sync legacy status if wrapper is kept.

## 5. Frame Video URL and Composition Spec

### Model/API Changes

Add `Frame.video_url`:

```python
video_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="帧视频片段URL")
```

Update serializers:

- `backend/v1/app/generate/service/video_generation.py` frame payload includes `video_url`.
- `backend/v1/app/generate/service/storyboard_service.py` includes `video_url` if frame dicts are returned.
- Frontend frame views use `frame.video_url` for segment preview and keep `frame.audio_url` for audio controls only.

Create a migration:

- add `frames.video_url varchar(500) null`.
- backfill only obvious MP4 values currently stored in `audio_url`:

```sql
UPDATE frames
SET video_url = audio_url,
    audio_url = NULL
WHERE audio_url IS NOT NULL
  AND (audio_url LIKE '%.mp4%' OR audio_url LIKE '%/frames/frame_%');
```

### Task Changes

In `generate_frame_video_task`:

- write `frame.video_url = video_url`
- do not touch `frame.audio_url`
- set `frame.dirty = 1`
- include `video_url` in step/task snapshots

In `compose_frames()`:

- if a frame has a syntactically valid HTTP `video_url` and is not dirty, attempt to download it and validate the local file with ffmpeg/moviepy before reuse. If download or validation fails, log the stale URL and fall back to regeneration.
- if generation fails for one frame, create a placeholder video for `float(frame.duration or 5)` seconds, mark `frame.status = 3`, set `error_message`, append placeholder, and continue.
- placeholder content should prefer a still-image segment from `frame.image_url` with a subtle overlay text such as `Frame {sequence} video failed`; if the image is unavailable, use a black 9:16 clip with the same overlay. The placeholder must be a valid MP4 and must not be an empty mock file in production paths.
- after composing all frames, if a `target_duration` is passed and final duration is longer, trim final output.
- enforce a per-frame generation timeout and an overall composition timeout. Recommended defaults: `FRAME_VIDEO_TIMEOUT_SECONDS=600` and `COMPOSE_TOTAL_TIMEOUT_SECONDS=max(900, frame_count * 600)`. Timeout should mark the affected frame failed and use the placeholder fallback.

Change signature:

```python
def compose_frames(self, frames: list[Frame], output_dir: str, target_duration: float | None = None) -> str:
```

Call with `project.target_duration` from `generate_video_task`.

### Scene Duration Fix

In `_generate_scene_video()`:

- keep model request duration constrained to provider rules if Seedance i2v requires 5 seconds.
- apply trim/extend after download to match `scene["duration"]`.
- remove misleading `duration = scene.get(...); duration = 5` overwrite or rename to `generation_duration`.

### Tests

Create `backend/tests/generate/test_video_composer.py`:

- failed middle frame uses placeholder and does not raise.
- stale `frame.video_url` download failure falls back to regeneration.
- `generate_frame_video_task` stores output in `video_url`, preserving existing `audio_url`.
- `_generate_scene_video()` honors scene duration through post-processing.
- `compose_frames(..., target_duration=...)` trims final output.
- per-frame timeout produces a failed frame plus placeholder instead of hanging forever.

## 6. Celery Task and Transaction Spec

### Failure State

Refactor `_mark_project_failed(db, project_id, stage)`:

- remove `db.commit()` from helper.
- helper only mutates loaded project.
- caller owns transaction boundary.
- delete the current try-block calls to `_mark_project_failed()` that immediately raise afterward. Those mutations would be rolled back by the outer `except`. Final project failure marking must happen only in `_update_task_failure_state()` after the main transaction rollback, followed by one explicit commit in the failure-state transaction.

Refactor `_update_task_failure_state()`:

- wrap all DB failure-state work in its own `try/except`.
- log failure-handler errors and never mask original task exception.
- when `will_retry=True`, increment `retry_count` in `_update_task_failure_state()` using the Celery retry count or `task.retry_count + 1`, then commit the retry-visible task state.
- if `will_retry=True`, keep project stage `running` and task status `queued` or `running`; do not mark project failed.
- if final failure and `stage` is set, mark failed and commit once.

Apply protected failure-handler pattern to:

- `generate_image_task`
- `generate_frame_image_task`
- `generate_frame_video_task`
- `export_video_task`

Frame-level failures:

- `generate_frame_image_task` should pass `stage="image"` on final failure.
- `generate_frame_video_task` should pass `stage="video"` on final failure.
- if product wants frame-level failure not to fail entire stage, set `stage_status="awaiting_review"` and expose failed frame ids. Pick one policy and test it. Recommended: final frame image failure marks image stage `failed`; final frame video failure marks video stage `failed`.

### Task Service

Change sync methods to fail loudly:

```python
def get_task_sync(self, db: Session, task_id: int) -> GenerationTask:
    task = db.get(GenerationTask, task_id)
    if not task:
        raise ValueError(f"generation task not found: {task_id}")
    return task
```

`start_task_sync()`:

- raise if missing.
- raise if task is terminal unless explicit `allow_restart=True`.
- clear `finished_at`, `error_code`, `error_message`.
- set `status="running"`.

`start_step_sync()`:

- raise if task missing.
- raise if task status is terminal.

`finish_step_sync()`:

- raise if step missing.

`create_task()`:

- add parameter `commit: bool = True`.
- when `commit=False`, call `db.flush()` and return task without committing.
- update call sites that need atomicity to use `commit=False` followed by a single caller-owned commit.

### Single-Frame Retry

Change `/projects/{project_id}/frames/{frame_id}/retry`:

- if frame failed in image phase or lacks `image_url`, enqueue `generate_frame_image_task`.
- if frame has image but failed video segment, enqueue `generate_frame_video_task`.
- do not call `submit_generation_task()`.
- return the new task id and frame id.

### TOS Compensation

Introduce `UploadedObjectTracker` in `video_tasks.py` or a small helper module:

```python
class UploadedObjectTracker:
    def __init__(self):
        self.keys = []
    def add(self, object_key: str):
        self.keys.append(object_key)
    def rollback(self):
        for key in reversed(self.keys):
            try:
                get_storage_client().delete_file(key)
            except Exception:
                logger.warning("failed to delete orphan upload %s", key, exc_info=True)
```

Use it for project audio, frame videos, final output, and export-derived outputs. If the storage client lacks delete support, add it to the client interface or record orphan uploads in a cleanup table/job.

### Idempotent Conversation Messages

Generation tasks that create assistant stage cards must be idempotent across Celery retries.

- `generate_image_task` should write the image-stage completion `Conversation` only after the final successful attempt.
- Before inserting an image-stage completion message, query for an existing `Conversation` with the same `project_id`, `task_id`, `stage="image"`, and `action_type="GENERATE_IMAGES"`. If it exists, update its blocks/metadata instead of inserting a duplicate.
- Apply the same `(project_id, task_id, stage, action_type)` idempotency rule to video-stage completion messages.
- Do not create new progress/stage-card messages from retry-visible failure paths.

### Task Cancellation

Add a minimal cancellation path for expensive generation tasks:

- API: `POST /generate/v1/tasks/{task_id}/cancel`.
- Validate task ownership with `generation_task_service.get_task(..., user_id)`.
- If `celery_task_id` exists and task status is `queued` or `running`, call Celery `revoke(celery_task_id, terminate=False)` first. Use `terminate=True` only if the deployment accepts hard process termination risk.
- Set task status to `cancelled`, `finished_at=now`, `current_step="CANCELLED"`.
- Mark the current project stage as `idle` if no output exists, or keep it `awaiting_review` if usable output from the previous successful generation remains. Do not erase existing confirmed outputs.
- Celery task code should check task status between major steps and exit early when status is `cancelled`.

### Tests

Create `backend/tests/generate/test_task_service.py`:

- missing task raises.
- starting terminal task raises.
- restarting with `allow_restart=True` clears `finished_at` and errors.
- `create_task(commit=False)` flushes id but does not commit.

Create `backend/tests/generate/test_video_tasks_failure.py`:

- retrying image task does not mark project failed.
- final failure marks stage failed once.
- try-block image/video failure branches do not call `_mark_project_failed()` before raising; final failure is committed only by `_update_task_failure_state()`.
- `retry_count` increments on each retry-visible failure update.
- failure-handler exception is logged and original exception is re-raised.
- frame retry endpoint queues frame task, not render task.
- retrying `generate_image_task` does not insert duplicate image-stage `Conversation` rows for the same task.
- cancelling a queued/running task updates task state and prevents later task steps from overwriting it back to `running`.

## 7. Data Model Integrity Spec

### ORM Updates

Modify models:

- `Project.user_id`: `ForeignKey("users.id", ondelete="SET NULL")`, `index=True`.
- `Project.product_id`: `ForeignKey("products.id", ondelete="SET NULL")`, `index=True`.
- `Project.last_task_id`: `ForeignKey("generation_tasks.id", ondelete="SET NULL")`, `index=True`.
- `Project.status`: `server_default="draft"`, `index=True`.
- `Frame.project_id`: `ForeignKey("projects.id", ondelete="CASCADE")`.
- `Frame`: add `UniqueConstraint("project_id", "sequence", name="uq_frames_project_sequence")`.
- `Script`: add unique constraint/index for `(project_id, version)`.
- `ProjectAsset`: add unique constraint for `(project_id, asset_id, role)`.
- `Conversation.task_id`: `ForeignKey("generation_tasks.id", ondelete="SET NULL")`, `index=True`.
- `Conversation.frame_id`: already FK; add `index=True`.
- `GenerationTask.current_frame_id`: `ForeignKey("frames.id", ondelete="SET NULL")`, `index=True`.
- `GenerationTaskStep.frame_id`: `ForeignKey("frames.id", ondelete="SET NULL")`, keep/add index.
- `Asset.user_id`: add `index=True`.

Add relationships:

- `Project.user`, `Project.product`, `Project.last_task`.
- `Conversation.frame`, `Conversation.task`.
- `Asset.user`, `Asset.project_bindings`.
- `ProjectAsset.project`, `ProjectAsset.asset`.
- optional `Frame.conversations`, `Frame.task_steps`.

### ProjectAsset Query Contract

Project detail must use `ProjectAsset` as the authoritative source for project-bound assets.

- Keep the existing precise `ProjectAsset -> Asset` join for bound assets.
- Remove broad URL-string matching for reference/library assets. URL fallback is allowed only for the generated output video when `project.video_output_url` exists but no `ProjectAsset(role="output")` row has been created yet.
- When creating generated output assets in `generate_video_task` and `export_video_task`, also create a `ProjectAsset` binding with `role="output"` or `role="export"` in the same transaction.
- `bind_project_asset` should be idempotent: if `(project_id, asset_id, role)` already exists, return the existing binding instead of raising.

### Migration Updates

Create one migration for additive safe changes:

- add `frames.video_url`.
- add missing indexes.
- add missing server defaults.
- add missing FKs where existing data is clean.
- add unique constraints after deduplicating rows.

Before adding constraints, run data cleanup queries:

- find duplicate `frames(project_id, sequence)`.
- find duplicate `scripts(project_id, version)`.
- find duplicate `project_assets(project_id, asset_id, role)`.
- find orphan project/user/product/task/frame references.

If orphans exist:

- set nullable references to `NULL` for `ondelete=SET NULL` columns.
- delete association rows with missing project/asset.
- fail migration with a clear message if required non-null references are invalid.

Production migration safety:

- Ship a dry-run audit command before the constraint migration. It should print counts and sample ids for duplicates and orphan references without changing data.
- Require human review of the dry-run report before running destructive cleanup in production.
- Put cleanup and constraint creation in separate migrations: first cleanup/backfill, then constraints/indexes.
- For every destructive cleanup query, write the affected rows to a timestamped backup table or export file before deleting/updating them.
- Document rollback: indexes/constraints can be dropped; data cleanup rollback requires restoring from backup tables or the pre-migration database backup.

### Legacy Status Lifecycle

`project.status` remains a denormalized legacy field for this remediation pass because frontend lists and old endpoints still read it. The source of truth is `workflow_stage + stage_status + dirty_stage`.

- All backend workflow mutations must call `sync_legacy_status()`.
- New code must not branch on `project.status` when equivalent workflow fields are available.
- Add a follow-up deprecation plan after frontend and API callers have moved to workflow fields: audit reads, remove writes outside `sync_legacy_status()`, then decide whether to keep `project.status` as a generated/cache column or drop it.

## 8. Frontend Spec

### Chat File Upload

Backend:

- Add an endpoint for chat with files, either:
  - `POST /generate/v1/projects/{project_id}/chat` accepts `multipart/form-data` with `content`, `frame_id`, and `files[]`, or
  - upload files first to asset API, then call chat with `asset_ids`.

Recommended: upload first, then chat with asset ids. This keeps chat payload JSON and reuses asset binding.

Frontend:

- Add `uploadAsset(file)` service using shared axios.
- In `useChat.sendMessage(content, files)`:
  - upload files.
  - bind uploaded asset ids to project.
  - call `sendChatMessage(activeProjectId, content, frameId, assetIds)`.
  - if upload fails, show assistant error and do not pretend files were processed.

### Shared Project Polling

Create `frontend/src/hooks/useProjectDetailStore.js` or use existing app store:

- one cache per `projectId`.
- one active timer per `projectId`.
- expose `project`, `frames`, `assets`, `loading`, `error`, `refetch`.
- `useWorkflowProject` and `useProjectPolling` become wrappers over the shared hook or are merged.

Polling rules:

- load once with `loading=true`.
- background refresh uses `refreshing=true`, not `loading=true`.
- poll only when `stage_status === "running"` or legacy status is in busy statuses.
- stop on terminal/idle statuses.

### MessageBlocks Actions

Add local state in `MessageBlocks`:

- `pendingActionKey`
- `actionError`

Disable all action buttons while one is pending. Show a compact inline error when API fails. Prevent duplicate clicks.

### API Client

`frontend/src/services/api.js`:

- set timeout, for example `timeout: 120000`.
- refresh token with body:

```javascript
axios.post('/api/generate/v1/auth/refresh', { refresh_token: refreshTokenValue }, { timeout: 30000 })
```

Backend auth refresh must accept JSON body and can keep query support temporarily for backward compatibility.

`frontend/src/services/auth.js` must also send refresh token in body.

### FrameGrid Prompt Replacement

Replace `prompt()` with a small modal component:

- title
- textarea
- cancel/confirm buttons
- loading state owned by caller

Use it for script regeneration, image regeneration, and retry.

### useProjects Cancellation

Add a cancellation flag or `AbortController` so unmounted components do not call `setProjects`, `setError`, or `setLoading`.

### KeyframeStudio

Move raw fetch into `frontend/src/services/keyframes.js`, using axios or a configured axios instance for `/opencv-api`. Include timeout and consistent error handling.

### Realtime Follow-Up

Do not implement SSE/WebSocket in this remediation pass. Create a separate realtime spec that covers:

- authentication strategy, preferably normal `Authorization: Bearer` when using `EventSource` polyfill or an http-only session cookie if using native `EventSource`.
- reconnect behavior using `Last-Event-ID`, exponential backoff, and a maximum fallback delay.
- switching logic between push and polling: push is primary when connected; polling becomes a slower fallback after disconnect.
- backend implementation choice, likely FastAPI `StreamingResponse` backed by database polling or Redis pub/sub.
- event schema for `project.updated`, `task.updated`, and `step.updated`.

## 9. Export and BGM Spec

### Export

`export_video_task` should produce a real derived output:

- download source `project.video_output_url`.
- if requested aspect ratio differs, crop/pad with ffmpeg.
- normalize codec to H.264/AAC MP4.
- upload to `projects/{project_id}/exports/{task_id}_{aspect_ratio}.mp4`.
- create `Asset` pointing to the exported object.
- store export metadata: source URL, aspect ratio, codec, duration, task id.

If only `9:16` is supported initially, still transcode/copy to a new export object so export tasks are real outputs and can be retried/cleaned independently.

### BGM

Re-enable BGM behind config:

- `settings.ENABLE_BGM_GENERATION`
- `settings.DEFAULT_BGM_VOLUME`

Use `frames[0].ai_params["bgm"]` or `project` metadata as description. If BGM generation fails, mark BGM step `skipped` or `failed_non_blocking` and continue with TTS-only video.

## 10. Workflow Agent Spec

For `workflow_stage == "image"`:

- if user text has image-edit intent but no frame id, ask which frame(s) with thumbnails or sequence options.
- if user text has general style/edit instruction and no specific frame, apply to all frames or ask confirmation depending on cost.
- if user says confirmation/next, advance to video.
- do not fall through to generic clarification when the intent is clearly image revision.

Add tests:

- image stage text "第 2 张图换成室内背景" resolves frame 2 and returns `REGENERATE_FRAME_IMAGE`.
- image stage text "整体更高级一点" returns `REGENERATE_FRAME_IMAGE` for all frames or a specific confirmation action, according to selected product policy.
- image stage text "继续生成视频" returns `CONFIRM_IMAGES_AND_GENERATE_VIDEO`.

## 11. Recommended Implementation Order

1. Add tests for workflow mapping, invalidation, task service terminal protections, and `Frame.video_url`.
2. Add `Frame.video_url` model/migration/API/frontend payload support.
3. Consolidate workflow state mutations into `project_workflow_state.py` and update call sites.
4. Refactor Celery failure handling and task service transaction behavior.
5. Fix frame retry and video composer fallback/duration handling.
6. Fix frontend API timeout/refresh body and action error handling.
7. Merge project polling hooks into one shared data source.
8. Implement chat file upload pipeline.
9. Add model FKs/indexes/relationships and data cleanup migration.
10. Implement export transcode and optional BGM.
11. Add task cancellation for queued/running generation tasks.
12. Write a separate SSE/WebSocket realtime spec after the core remediation is stable.

## 12. Acceptance Criteria

1. Single-frame video generation never overwrites `frame.audio_url`; `frame.video_url` contains the generated MP4 URL.
2. Retried Celery tasks do not visibly mark projects failed until retries are exhausted.
3. `project.status`, `workflow_stage`, `stage_status`, and `dirty_stage` stay consistent after every workflow mutation.
4. Invalidating image regresses to script confirmed with `dirty_stage="image"`; invalidating video regresses to image confirmed with `dirty_stage="video"`; invalidated stages never masquerade as reviewable output.
5. Image awaiting review and image confirmed no longer show as script-ready unless intentionally documented as the legacy compatibility label.
6. Video awaiting review does not display as processing.
7. A failed frame video segment no longer aborts all composition; a valid placeholder segment with frame-duration timing is used and failure is visible on the frame.
8. Stale `frame.video_url` values fall back to regeneration after failed download/validation.
9. Existing successful frame images are skipped during render.
10. Image/video stage-card conversations are idempotent per task and are not duplicated by retries.
11. Chat file attachments arrive at backend as assets or multipart files and are visible in project detail through `ProjectAsset`.
12. Project detail is fetched by only one active polling loop per active project in normal UI usage.
13. Recursive polling no longer flashes the full loading UI.
14. Workflow buttons cannot be double-clicked into duplicate requests and show API failures.
15. Missing task/step ids raise explicit errors in sync task service methods.
16. Terminal tasks cannot be moved back to running without explicit restart intent.
17. `retry_count` increments during retry-visible failure updates.
18. Queued/running generation tasks can be cancelled without later step updates resurrecting them as running.
19. Refresh tokens are not sent in URLs.
20. Axios requests have bounded timeouts.
21. Frame editing no longer uses browser `prompt()`.
22. ORM model metadata matches migration constraints and expected referential integrity.
23. Destructive data cleanup migrations have a dry-run audit, human review gate, backup, and rollback notes.
24. Export task creates a real export asset, not just an alias to the source video.
