from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message


def test_real_chinese_video_prompt_creates_project():
    prompt = "帮我生成一个蓝牙耳机带货短视频，突出降噪、续航和佩戴舒适。"

    result = classify_no_project_message(prompt)

    assert result["should_create_project"] is True
    assert result["action"] == "CREATE_PROJECT"
