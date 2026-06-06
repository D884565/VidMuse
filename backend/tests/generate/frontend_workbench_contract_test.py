from pathlib import Path


def test_frontend_has_storyboard_timeline_component():
    source = Path("frontend/src/components/Workflow/StoryboardTimeline.jsx").read_text(encoding="utf-8")

    assert "dirty" in source
    assert "duration" in source
    assert "status" in source


def test_frontend_project_service_has_export_and_asset_methods():
    source = Path("frontend/src/services/project.js").read_text(encoding="utf-8")

    assert "downloadProjectVideo" in source
    assert "responseType: 'blob'" in source or 'responseType: "blob"' in source
    assert "getProjectScript" in source
    assert "bindProjectAsset" in source


def test_vite_api_proxy_targets_local_backend_port_8010_by_default():
    source = Path("frontend/vite.config.js").read_text(encoding="utf-8")

    assert "env.VITE_API_TARGET || 'http://localhost:8010'" in source


def test_frontend_project_service_keeps_pending_action_endpoints_for_backend_compat():
    project_service = Path("frontend/src/services/project.js").read_text(encoding="utf-8")

    assert "confirmPendingAction" in project_service
    assert "cancelPendingAction" in project_service
    assert "pending-actions" in project_service


def test_project_polling_does_not_treat_script_ready_as_terminal():
    source = Path("frontend/src/hooks/useProjectPolling.js").read_text(encoding="utf-8")

    # 终态判断应基于 workflow 字段，不依赖旧 status 字符串
    assert "TERMINAL_STATUSES" not in source  # 已移除旧常量
    assert "isProjectTerminal" in source  # 使用 workflow 字段推导终态
    assert "stage_status === 'running'" in source
    assert "script_ready" not in source  # 不应硬编码旧 status 值


def test_frame_grid_uses_workflow_status_for_busy_and_render_controls():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "project?.stage_status === 'running'" in source
    assert "project?.workflow_stage === 'video'" in source


def test_frame_grid_has_single_frame_video_regenerate_and_edit_entrypoints():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "regenerateFrameVideo" in source
    assert "updateFrame" in source
    assert "handleRegenerateVideo" in source
    assert "handleSaveFrameEdit" in source


def test_frame_grid_polls_active_task_and_surfaces_retry_and_action_guidance():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "setInterval" in source
    assert "RETRYING" in source
    assert "actionMessage" in source


def test_frame_grid_uses_direct_download_export_flow():
    source = Path("frontend/src/components/Keyframes/FrameGrid.jsx").read_text(encoding="utf-8")

    assert "downloadProjectVideo" in source
    assert "exportProjectVideo" not in source
    assert "Download started" in source or "download has started" in source.lower()


def test_api_service_preserves_blob_download_responses():
    source = Path("frontend/src/services/api.js").read_text(encoding="utf-8")

    assert "response.config?.responseType === 'blob'" in source or 'response.config?.responseType === "blob"' in source
    assert "return response" in source


def test_project_detail_fetches_full_latest_script_for_storyboard_panel():
    source = Path("frontend/src/components/Project/ProjectDetail.jsx").read_text(encoding="utf-8")

    assert "getProjectScript" in source
    assert "latestScriptSummary?.id" in source
    assert "scriptDetail?.content" in source
    assert "frame?.description" in source
    assert "frame?.narration" in source


def test_project_download_rejects_blob_error_payloads_instead_of_saving_fake_mp4():
    source = Path("frontend/src/services/project.js").read_text(encoding="utf-8")

    assert "await response.data.text()" in source
    assert "JSON.parse(errorText)" in source
    assert "throw new Error(errorPayload.message || '导出失败')" in source or 'throw new Error(errorPayload.message || "导出失败")' in source


def test_chat_container_uses_same_project_detail_hook_as_frame_grid():
    source = Path("frontend/src/components/Chat/ChatContainer.jsx").read_text(encoding="utf-8")

    assert "useProjectPolling" in source
    assert "useWorkflowProject" not in source


def test_workbench_view_is_single_column_conversation_not_split_canvas():
    source = Path("frontend/src/components/Workbench/WorkbenchView.jsx").read_text(encoding="utf-8")

    assert "chatWidth" not in source
    assert "cursor-col-resize" not in source
    assert "canvasPanel" not in source
    assert "FrameCard" not in source
    assert "max-w-5xl" in source or "max-w-6xl" in source


def test_message_blocks_does_not_render_workflow_action_bar_buttons():
    source = Path("frontend/src/components/Chat/MessageBlocks.jsx").read_text(encoding="utf-8")

    assert "function ActionBar" not in source
    assert "confirmWorkflowStage" not in source
    assert "advanceWorkflowStage" not in source
    assert "block.type === 'action_bar'" not in source


def test_message_blocks_replaces_inline_edit_buttons_with_conversational_follow_up():
    source = Path("frontend/src/components/Chat/MessageBlocks.jsx").read_text(encoding="utf-8")

    assert "保存修改" not in source
    assert "重新生成图片" not in source
    assert "重新生成视频" not in source
    assert "确认执行" not in source
    assert "这个版本你想怎么调？" in source
    assert "方向有没有要调的？" in source


def test_streaming_chat_parser_handles_sse_error_events():
    source = Path("frontend/src/services/chat.js").read_text(encoding="utf-8")

    assert "else if (eventType === 'error')" in source
    assert "onError?.(" in source


def test_no_project_chat_uses_entry_stream_before_create_project():
    chat_service = Path("frontend/src/services/chat.js").read_text(encoding="utf-8")
    use_chat = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")

    assert "sendEntryChatMessageStream" in chat_service
    assert "/chat/entry/stream" in chat_service
    assert "sendEntryChatMessageStream" in use_chat
    assert "CREATE_PROJECT" in use_chat


def test_sidebar_shows_local_draft_conversation_before_project_creation():
    store_source = Path("frontend/src/store/appStore.js").read_text(encoding="utf-8")
    list_source = Path("frontend/src/components/Project/ProjectList.jsx").read_text(encoding="utf-8")
    use_chat = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")

    assert "draftConversationTitle" in store_source
    assert "setDraftConversationTitle" in store_source
    assert "draftConversationTitle" in list_source
    assert "普通对话" in list_source
    assert "setDraftConversationTitle(trimmedContent)" in use_chat or "setDraftConversationTitle(content.trim())" in use_chat
    assert "clearDraftConversation" in use_chat


def test_project_creation_keeps_draft_chat_visible_until_backend_history_catches_up():
    use_chat = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")
    chat_state = Path("frontend/src/hooks/chatState.js").read_text(encoding="utf-8")

    assert "promoteDraftMessagesToProject" in chat_state
    assert "promoteDraftMessagesToProject(current, project.id, assistantMsgId)" in use_chat
    assert "mergeFetchedMessages(existing, normalized, streamingMessageId)" in use_chat


def test_project_creation_auto_triggers_script_generation_from_entry_chat():
    use_chat = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")

    assert "generateProjectScript" in use_chat
    assert "await generateProjectScript(projectId)" in use_chat or "await generateProjectScript(project.id)" in use_chat


def test_draft_chat_state_is_persisted_beyond_sidebar_title():
    chat_state = Path("frontend/src/hooks/chatState.js").read_text(encoding="utf-8")
    store_source = Path("frontend/src/store/appStore.js").read_text(encoding="utf-8")

    assert "readPersistedDraftState" in chat_state
    assert "writePersistedDraftState" in chat_state
    assert "clearPersistedDraftState" in chat_state
    assert "draftConversationMessages" in store_source


def test_project_creation_for_entry_chat_forwards_selected_assets():
    use_chat = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")

    assert "selected_assets: submission.selectedAssets" in use_chat


def test_backend_material_flow_no_longer_injects_raw_material_text_or_image_urls():
    generation_source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    chat_service_source = Path("backend/v1/app/generate/service/chat/chat_service.py").read_text(encoding="utf-8")
    project_dao_source = Path("backend/v1/app/generate/dao/project.py").read_text(encoding="utf-8")

    assert "MaterialResolver" in generation_source
    assert "selected_assets" in project_dao_source
    assert "material_text_reference" not in generation_source
    assert "material_reference_images" not in generation_source
    assert "_apply_selected_assets_to_project" not in chat_service_source


def test_project_card_displays_generation_suffix_without_mutating_project_title():
    source = Path("frontend/src/components/Project/ProjectCard.jsx").read_text(encoding="utf-8")

    assert "getSidebarProjectTitle(project)" in source
    assert "带货视频生成" in source
    assert "未命名视频项目" in source


def test_project_card_derives_sidebar_status_from_workflow_fields():
    source = Path("frontend/src/components/Project/ProjectCard.jsx").read_text(encoding="utf-8")

    assert "getWorkflowStatusDisplay(project)" in source
    assert "workflow_stage" in source
    assert "stage_status" in source
    assert "视频待确认" in source
    assert "图片待确认" in source


def test_project_list_refresh_keeps_existing_items_visible():
    source = Path("frontend/src/hooks/useProjects.js").read_text(encoding="utf-8")

    assert "setLoading(projects.length === 0)" in source
    assert "setLoading(true)" not in source


def test_empty_streaming_assistant_message_does_not_render_lonely_cursor_bubble():
    source = Path("frontend/src/components/Chat/MessageBubble.jsx").read_text(encoding="utf-8")

    assert "hasRenderableContent" in source
    assert "return null" in source


def test_active_frontend_paths_do_not_import_removed_legacy_modules():
    for path in (
        "frontend/src/components/Layout/MainLayout.jsx",
        "frontend/src/components/Layout/Sidebar.jsx",
        "frontend/src/components/Chat/ChatContainer.jsx",
        "frontend/src/components/Keyframes/FrameGrid.jsx",
        "frontend/src/hooks/useChat.js",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "useWorkflowProject" not in source
        assert "KeyframeStudio" not in source
        assert "MergePanel" not in source
        assert "useFileUpload" not in source
        assert "FilePreview" not in source


def test_chat_input_does_not_offer_fake_file_send_path():
    use_chat_source = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")
    input_source = Path("frontend/src/components/Input/SmartInput.jsx").read_text(encoding="utf-8")

    assert "files = []" not in use_chat_source
    assert "onSend(value, files)" not in input_source


def test_use_chat_keeps_per_project_streaming_cache_when_switching_projects():
    source = Path("frontend/src/hooks/useChat.js").read_text(encoding="utf-8")

    assert "messagesByProject" in source
    assert "streamingProjectKeyRef" in source
    assert "mergeFetchedMessages" in source
    assert "getProjectMessages(messagesByProject, activeProjectId)" in source
