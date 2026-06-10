"""商品信息数据类"""
from dataclasses import dataclass, field


@dataclass
class ProductInfo:
    """从商品URL抓取的结构化商品信息"""

    title: str = ""
    """商品标题"""

    price: str = ""
    """商品价格（字符串，保留原格式如 "¥99.00"）"""

    original_price: str = ""
    """原价"""

    main_images: list[str] = field(default_factory=list)
    """主图URL列表"""

    detail_images: list[str] = field(default_factory=list)
    """详情图URL列表"""

    description: str = ""
    """商品描述/卖点"""

    ai_features: dict = field(default_factory=dict)
    """AI解析结果特征，包含规格、标签等所有结构化信息"""

    platform: str = ""
    """来源平台：taobao/jd/pdd/douyin"""

    url: str = ""
    """原始商品URL"""

    @property
    def is_empty(self) -> bool:
        """是否所有字段都为空"""
        return not (self.title or self.price or self.main_images)

    def to_prompt_text(self) -> str:
        """转换为LLM prompt可用的文本格式"""
        parts = []
        if self.title:
            parts.append(f"商品名称：{self.title}")
        if self.price:
            parts.append(f"价格：{self.price}")
        if self.original_price:
            parts.append(f"原价：{self.original_price}")
        if self.description:
            parts.append(f"商品描述：{self.description}")
        # 从ai_features中提取规格参数
        parameters = self.ai_features.get("parameters", {})
        if parameters:
            specs_text = "、".join(f"{k}:{v}" for k, v in parameters.items())
            parts.append(f"规格参数：{specs_text}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "title": self.title,
            "price": self.price,
            "original_price": self.original_price,
            "main_images": self.main_images,
            "detail_images": self.detail_images,
            "description": self.description,
            "ai_features": self.ai_features,
            "platform": self.platform,
            "url": self.url,
        }
