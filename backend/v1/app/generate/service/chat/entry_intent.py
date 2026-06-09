from __future__ import annotations

import re


def classify_no_project_message(content: str) -> dict:
    """Classify a message before a project exists."""
    text = (content or "").strip()
    if not text:
        return {"action": "CONVERSE", "should_create_project": False}

    if _has_project_creation_intent(text):
        return {"action": "CREATE_PROJECT", "should_create_project": True}

    return {
        "action": "CONVERSE",
        "should_create_project": False,
        "assistant_content": _entry_converse_reply(text),
    }


def _has_project_creation_intent(text: str) -> bool:
    if re.search(r"https?://\S+", text):
        return True

    creation_words = ("生成", "制作", "做一个", "来一个", "创建", "帮我做", "帮我生成", "创作")
    video_words = ("视频", "短视频", "广告", "带货", "商品", "产品", "推广", "宣传", "种草", "宣传片")
    script_words = ("剧本", "分镜", "脚本")

    has_creation = any(word in text for word in creation_words)
    has_video_target = any(word in text for word in video_words)
    has_script_target = any(word in text for word in script_words)
    return has_creation and (has_video_target or has_script_target)


def _entry_converse_reply(text: str) -> str:
    greeting_words = ("你好", "您好", "hello", "hi", "嗨")
    if any(word in text.lower() for word in greeting_words):
        return "你好，我在。你可以随便问我关于带货视频创作、脚本、分镜、首帧图或配音的问题；只有当你明确说要生成某个视频项目时，我才会创建项目。"
    return "我先按普通问题来回答，不会创建项目。你可以继续提问；如果想开始做视频，请直接说例如「生成一个耳机带货视频」。"
