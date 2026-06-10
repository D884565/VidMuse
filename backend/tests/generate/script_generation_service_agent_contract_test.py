import asyncio
from types import SimpleNamespace

from backend.v1.app.script.service.script_generation_service import ScriptGenerationService


class _FakeScriptAgent:
    def __init__(self):
        self.calls = []

    async def generate_script(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "video_meta": {
                "product_name": kwargs["project_info"].get("商品标题", ""),
                "target_duration": kwargs["target_duration"],
                "style": "lifestyle",
                "aspect_ratio": "9:16",
                "hook_line": "马上看",
            },
            "scenes": [
                {
                    "scene_id": 1,
                    "type": "hook",
                    "duration": 5,
                    "text": "开场文案",
                    "voice_style": "excited",
                    "visual": {
                        "image_prompt": "明亮产品特写",
                        "video_prompt": "镜头推进",
                        "camera": "push_in",
                        "mood": "bright",
                        "overlay": {
                            "text": "",
                            "position": "bottom",
                            "style": "highlight",
                        },
                    },
                }
            ],
            "audio": {
                "tts_voice": "zh_female_cancan_mars_bigtts",
                "bgm": "轻快",
                "bgm_volume": 0.3,
            },
        }


def _build_project(**overrides):
    data = {
        "title": "便携榨汁杯",
        "description": "夏日冷饮小家电",
        "product_info": None,
        "user_prompt": "做一个种草短视频",
        "style": "清爽",
        "target_audience": "上班族",
        "key_points": ["便携", "续航久"],
        "avoid": [],
        "reference_images": [],
        "product_id": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_call_agent_accepts_project_without_category_attribute():
    service = ScriptGenerationService()
    service._script_agent = _FakeScriptAgent()
    project = _build_project()

    result = asyncio.run(service._call_agent(None, "prompt", project, 15))

    assert result["scenes"][0]["text"] == "开场文案"


def test_call_agent_passes_trace_context_to_script_agent():
    service = ScriptGenerationService()
    fake_agent = _FakeScriptAgent()
    service._script_agent = fake_agent
    project = _build_project(id=321, user_id=654)

    asyncio.run(service._call_agent(None, "prompt", project, 15))

    call_kwargs = fake_agent.calls[-1]
    context = call_kwargs["context"]
    assert context["project_id"] == 321
    assert context["user_id"] == 654
    assert context["session_id"] == "script_project_321"
    assert context["meta_data"]["source"] == "script_generation_service"
