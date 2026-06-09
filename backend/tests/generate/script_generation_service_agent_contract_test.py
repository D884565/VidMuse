import asyncio
from types import SimpleNamespace

from backend.v1.app.script.service.script_generation_service import ScriptGenerationService


class _FakeScriptAgent:
    async def generate_script(self, **kwargs):
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


def test_call_agent_accepts_project_without_category_attribute():
    service = ScriptGenerationService()
    service._script_agent = _FakeScriptAgent()
    project = SimpleNamespace(
        title="便携榨汁杯",
        description="夏日冷饮小家电",
        product_info=None,
        user_prompt="做一个种草短视频",
        style="清爽",
        target_audience="上班族",
        key_points=["便携", "续航久"],
        avoid=[],
        reference_images=[],
        product_id=None,
    )

    result = asyncio.run(service._call_agent(None, "prompt", project, 15))

    assert result["scenes"][0]["text"] == "开场文案"
