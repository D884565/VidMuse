from types import SimpleNamespace
from unittest.mock import patch

from backend.v1.app.generate.service.chat.intent_service import classify_entry_intent


def test_explicit_video_request_still_creates_project_when_llm_says_false():
    prompt = "帮我生成一个蓝牙耳机带货短视频，突出降噪、续航和佩戴舒适。"

    with patch("backend.v1.app.generate.service.chat.intent_service.VolcanoLLM") as mock_llm:
        mock_llm.return_value._chat.return_value = SimpleNamespace(
            content='{"should_create_project": false, "reason": "misclassified"}'
        )

        result = classify_entry_intent(prompt)

    assert result["should_create_project"] is True
