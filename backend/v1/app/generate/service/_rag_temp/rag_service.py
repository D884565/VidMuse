"""RAG 服务接口定义"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, List


@dataclass
class RAGResult:
    """RAG 检索结果"""
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    url: Optional[str] = None


class RAGService(Protocol):
    """RAG 服务接口协议"""

    async def search_scripts(
        self, query: str, top_k: int = 5
    ) -> List[RAGResult]:
        """检索相似商品的带货剧本模板"""
        ...

    async def search_assets(
        self, query: str, image_url: Optional[str] = None, top_k: int = 5
    ) -> List[RAGResult]:
        """检索相似视觉素材"""
        ...

    async def search_product_knowledge(
        self, query: str, top_k: int = 5
    ) -> List[RAGResult]:
        """检索商品知识库"""
        ...


class MockRAGService:
    """RAG 服务 Mock 实现，用于开发阶段"""

    async def search_scripts(
        self, query: str, top_k: int = 5
    ) -> List[RAGResult]:
        return [
            RAGResult(
                id="mock_script_1",
                content="开场hook：「还在为选XX发愁？这款XX让你一步到位！」\n卖点展示：「采用XX工艺，XX材质，用过的都说好」\n价格锚定：「原价XX，今天直播间专属价只要XX」",
                metadata={"type": "hook_selling_price", "category": "general"},
                score=0.95,
            ),
            RAGResult(
                id="mock_script_2",
                content="紧迫感：「库存只剩最后XX件，拍完就恢复原价」\n行动号召：「点击下方小黄车，立即下单！」",
                metadata={"type": "urgency_cta", "category": "general"},
                score=0.88,
            ),
        ]

    async def search_assets(
        self, query: str, image_url: Optional[str] = None, top_k: int = 5
    ) -> List[RAGResult]:
        return [
            RAGResult(
                id="mock_asset_1",
                content="产品特写镜头：柔和侧光照明，浅景深，高端产品摄影风格",
                metadata={"scene": "product_closeup", "mood": "elegant"},
                score=0.90,
            ),
        ]

    async def search_product_knowledge(
        self, query: str, top_k: int = 5
    ) -> List[RAGResult]:
        return [
            RAGResult(
                id="mock_knowledge_1",
                content="品质保证，正品行货；性价比高，同价位最优；用户好评率98%；支持7天无理由退换",
                metadata={"source": "product_knowledge"},
                score=0.92,
            ),
        ]
