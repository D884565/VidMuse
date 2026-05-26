"""解析器基类"""
import logging
from abc import ABC, abstractmethod

from backend.v1.app.product.dao.product_info import ProductInfo

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """商品页面解析器基类"""

    @abstractmethod
    def parse(self, html: str, url: str) -> ProductInfo:
        """
        解析商品页面HTML，提取结构化信息。

        :param html: 页面HTML内容
        :param url: 商品URL
        :returns: ProductInfo 结构化数据
        """
        pass

    def _clean_text(self, text: str) -> str:
        """清理文本（去除多余空白）"""
        if not text:
            return ""
        return " ".join(text.split()).strip()

    def _extract_image_urls(self, elements, attr: str = "src") -> list[str]:
        """从HTML元素中提取图片URL"""
        urls = []
        for el in elements:
            url = el.get(attr, "")
            if url and url.startswith("http"):
                urls.append(url)
        return urls
