import json

from backend.v1.app.generate.service.image_generation_service import ImageGenerationService
from backend.v1.app.generate.service.image_workflow import ImageWorkflowService, build_image_stage_message


class Frame:
    id = 1
    sequence = 1
    image_url = "https://cdn.test/1.png"
    status = 2
    error_message = None
    description = "商品在桌面上"


def test_build_image_stage_message_contains_image_grid_and_actions():
    message = build_image_stage_message([Frame()], task_id=9)
    block_types = [block["type"] for block in message["blocks"]]

    assert "image_grid" in block_types
    assert "action_bar" in block_types
    assert message["task_id"] == 9


def test_image_workflow_reference_images_prefer_user_uploads_over_product_images():
    project = type("Project", (), {})()
    project.reference_images = ["https://cdn.test/user-reference.png"]
    project.product_info = json.dumps({
        "main_images": ["https://cdn.test/product-main.png"],
    })

    reference_images = ImageWorkflowService()._extract_reference_images(project)

    assert reference_images == [
        "https://cdn.test/user-reference.png",
        "https://cdn.test/product-main.png",
    ]


def test_generate_frame_images_uses_reference_images_and_augments_prompt(monkeypatch):
    service = ImageGenerationService()
    calls = {}
    frame = Frame()
    frame.description = "商品在桌面上，柔和自然光"
    frame.status = 0
    frame.image_url = None

    def fake_image_to_image(prompt, reference_image_urls):
        calls["prompt"] = prompt
        calls["reference_image_urls"] = reference_image_urls
        return "local.png"

    monkeypatch.setattr(service, "_call_image_to_image", fake_image_to_image)
    monkeypatch.setattr(service, "_upload_to_tos", lambda path, project_id, index: "https://cdn.test/generated.png")

    service.generate_frame_images(
        [frame],
        project_id=1,
        reference_images=[
            "https://cdn.test/user-reference.png",
            "https://cdn.test/product-main.png",
        ],
    )

    assert calls["reference_image_urls"] == [
        "https://cdn.test/user-reference.png",
        "https://cdn.test/product-main.png",
    ]
    assert "请参考输入图片" in calls["prompt"]
    assert "商品在桌面上，柔和自然光" in calls["prompt"]
    assert frame.image_url == "https://cdn.test/generated.png"


def test_image_generation_payload_uses_vertical_size_for_text_to_image(monkeypatch, tmp_path):
    service = ImageGenerationService()
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"url": "https://ark.test/generated.png"}]}

    def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return Response()

    monkeypatch.setattr(service, "_request_with_retry", fake_request)
    monkeypatch.setattr(service, "_download_image", lambda url, path: tmp_path.joinpath("image.png").write_text("ok"))

    service._call_text_to_image("竖屏商品图")

    assert captured["json"]["size"] == "1600x2848"
    assert captured["json"]["sequential_image_generation"] == "disabled"
    assert "image" not in captured["json"]


def test_image_generation_payload_sends_multiple_reference_images(monkeypatch, tmp_path):
    service = ImageGenerationService()
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"url": "https://ark.test/generated.png"}]}

    def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return Response()

    monkeypatch.setattr(service, "_request_with_retry", fake_request)
    monkeypatch.setattr(service, "_download_image", lambda url, path: tmp_path.joinpath("image.png").write_text("ok"))

    service._call_image_to_image(
        "竖屏商品图",
        [
            "https://cdn.test/user-reference.png",
            "https://cdn.test/product-main.png",
        ],
    )

    assert captured["json"]["image"] == [
        "https://cdn.test/user-reference.png",
        "https://cdn.test/product-main.png",
    ]
    assert captured["json"]["size"] == "1600x2848"
    assert captured["json"]["sequential_image_generation"] == "disabled"
