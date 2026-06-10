from backend.v1.app.pipeline.base import PipelineContext
from backend.v1.app.pipeline.processors.img.product_understanding_processor import ProductUnderstandingProcessor


class _FakeLlm:
    def image_understanding(self, request):
        self.request = request
        class _Resp:
            content = '{"商品名称":"测试商品","核心卖点":["便携"]}'

        return _Resp()


def test_product_understanding_processor_uses_first_image_url_for_request():
    fake_llm = _FakeLlm()
    processor = ProductUnderstandingProcessor(llm_client=fake_llm)
    context = PipelineContext(
        {
            "images": ["https://example.com/a.png", "https://example.com/b.png"],
            "description": "sample product",
        }
    )

    processor.process(context)

    assert fake_llm.request.image_url == "https://example.com/a.png"
    assert context.get("product_understanding")["商品名称"] == "测试商品"
