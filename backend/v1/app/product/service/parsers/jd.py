"""京东商品页面解析器"""
import json
import logging
import re

from bs4 import BeautifulSoup

from backend.v1.app.product.dao.product_info import ProductInfo
from backend.v1.app.product.service.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class JdParser(BaseParser):
    """京东商品页面解析器"""

    def parse(self, html: str, url: str) -> ProductInfo:
        soup = BeautifulSoup(html, "html.parser")
        info = ProductInfo(platform="jd", url=url)

        try:
            # 标题
            title_el = soup.select_one(".sku-name, .itemInfo-wrap .item-name, h1")
            if title_el:
                info.title = self._clean_text(title_el.get_text())

            # 价格（京东价格通常通过API加载，尝试从页面脚本中提取）
            price_match = re.search(r'\"p\":\"([^\"]+)\"', html)
            if price_match:
                info.price = f"¥{price_match.group(1)}"
            else:
                # 降级：从DOM提取
                price_el = soup.select_one(".p-price .price, .J-p-price")
                if price_el:
                    price_text = self._clean_text(price_el.get_text())
                    price_num = re.search(r'(\d+\.?\d*)', price_text)
                    if price_num:
                        info.price = f"¥{price_num.group(1)}"

            # 主图（京东图片多为懒加载，尝试多种属性）
            img_elements = soup.select("#spec-list img, .lh-lazy img, [class*='main-img'] img, .sku-main-img img")
            info.main_images = (
                self._extract_image_urls(img_elements, attr="data-url") or
                self._extract_image_urls(img_elements, attr="data-lazy-img") or
                self._extract_image_urls(img_elements, attr="src") or
                self._extract_images_from_script(soup)
            )

            # 如果还是没有，从整个HTML中提取京东CDN图片
            if not info.main_images:
                html_str = str(soup)
                cdn_urls = re.findall(r'(https?://m\.360buyimg\.com/[^\"\'\\s]+)', html_str)
                info.main_images = list(set(cdn_urls))[:10]

            # 规格参数
            spec_elements = soup.select(".Ptable-item dl, .sku-details .item")
            for dl in spec_elements:
                dts = dl.select("dt")
                dds = dl.select("dd")
                for dt, dd in zip(dts, dds):
                    key = self._clean_text(dt.get_text())
                    value = self._clean_text(dd.get_text())
                    if key and value:
                        info.specs[key] = value

            # 描述
            desc_el = soup.select_one("#description, .detail-content, [class*='desc']")
            if desc_el:
                info.description = self._clean_text(desc_el.get_text())

        except Exception as e:
            logger.warning(f"[京东解析] 解析失败: {e}")

        return info

    def _extract_images_from_script(self, soup: BeautifulSoup) -> list[str]:
        """从页面脚本中提取图片URL"""
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            # 查找 imageList 数据
            if "imageList" in text or "itemImages" in text:
                urls = re.findall(r'https?://[^"\']+\.(?:jpg|png|webp)', text)
                return [u for u in urls if "jd.com" in u or "360buyimg.com" in u]
        return []
