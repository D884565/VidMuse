import asyncio
from types import SimpleNamespace

from backend.v1.app.generate.service.chat.parsed_material_prompt import format_material_prompt_section
from backend.v1.app.generate.service.stages.script import ScriptGenerationService


def test_format_material_prompt_section_groups_strategy_and_product_points():
    materials = [
        {
            "title": "viral sample",
            "prompt_summary": {
                "strategy_points": ["lead with pain point", "stack selling points in the middle"],
                "selling_points": ["portable", "long battery life"],
                "visual_points": ["transparent cup body"],
                "audience": "office commuters",
                "scenarios": ["office"],
                "keywords": ["fresh blend"],
            },
        }
    ]

    text = format_material_prompt_section(materials)

    assert "Material analysis reference" in text
    assert "Viral video strategy reference" in text
    assert "Product feature reference" in text
    assert "lead with pain point" in text
    assert "portable" in text
    assert "directly copy" in text


def test_format_material_prompt_section_returns_empty_for_no_materials():
    assert format_material_prompt_section([]) == ""


def test_script_build_prompt_appends_material_reference_section():
    service = ScriptGenerationService(rag_service=object())
    project = SimpleNamespace(
        title="portable blender",
        description="summer drink helper",
        product_info=None,
        user_prompt="make a product video",
        reference_images=[],
        style=None,
        target_audience=None,
        key_points=[],
        avoid=[],
    )

    from backend.v1.app.generate.service.stages import script as script_module

    original_loader = script_module._load_prompt
    script_module._load_prompt = lambda name: {
        "script_user_intent": "USER:{user_prompt}",
        "script_supplement": "STRUCT:{structured_fields}",
        "script_product_info": "PRODUCT:{title}|{description}|{product_detail}",
        "script_reference_images": "IMAGES:{images_text}",
        "script_generation": "{core_sections}\n{reference}\n{target_duration}",
    }[name]
    try:
        prompt = service._build_prompt(
            project,
            target_duration=15,
            reference="",
            material_reference="## Material analysis reference\nViral video strategy reference: lead with pain point",
        )
    finally:
        script_module._load_prompt = original_loader

    assert "Material analysis reference" in prompt
    assert "lead with pain point" in prompt


def test_build_material_reference_reads_bound_asset_prompt_summaries():
    service = ScriptGenerationService(rag_service=object())

    class FakeScalarResult:
        def __init__(self, values):
            self._values = values

        def all(self):
            return self._values

    class FakeExecuteResult:
        def __init__(self, values):
            self._values = values

        def scalars(self):
            return FakeScalarResult(self._values)

    class FakeDb:
        async def execute(self, _query):
            return FakeExecuteResult([
                SimpleNamespace(
                    id=101,
                    title="viral sample",
                    ai_features={
                        "prompt_summary": {
                            "strategy_points": ["lead with pain point"],
                            "selling_points": ["portable"],
                            "visual_points": ["transparent cup body"],
                            "audience": "office commuters",
                            "scenarios": ["office"],
                            "keywords": ["fresh blend"],
                            "reference_text": "unused here",
                        }
                    },
                )
            ])

    text = asyncio.run(service._build_material_reference(FakeDb(), 55))

    assert "Material analysis reference" in text
    assert "lead with pain point" in text
    assert "portable" in text
