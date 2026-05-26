"""拼多多商品页面解析器"""
import json
import logging
import re

from bs4 import BeautifulSoup

from backend.v1.app.product.dao.product_info import ProductInfo
from backend.v1.app.product.service.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class PddParser(BaseParser):
    """拼多多商品页面解析器"""

    def parse(self, html: str, url: str) -> ProductInfo:
        soup = BeautifulSoup(html, "html.parser")
        info = ProductInfo(platform="pdd", url=url)

        try:
            # 拼多多页面多为动态渲染，尝试从脚本中提取数据
            script_data = self._extract_json_data(soup)
            if script_data:
                info = self._parse_json_data(info, script_data)
            else:
                # 降级：从DOM提取
                info = self._parse_from_dom(soup, info)

        except Exception as e:
            logger.warning(f"[拼多多解析] 解析失败: {e}")

        return info

    def _extract_json_data(self, soup: BeautifulSoup) -> dict | None:
        """从页面脚本中提取商品JSON数据"""
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            # 查找 window.__rawData 或类似数据
            if "__rawData" in text or "goods" in text:
                try:
                    match = re.search(r'window\.__rawData\s*=\s*({.*?});', text, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))
                except (json.JSONDecodeError, AttributeError):
                    pass

                # 尝试查找 goods 数据
                try:
                    match = re.search(r'"goods"\s*:\s*({.*?})\s*[,}]', text, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))
                except (json.JSONDecodeError, AttributeError):
                    pass

        return None

    def _parse_json_data(self, info: ProductInfo, data: dict) -> ProductInfo:
        """从JSON数据中提取商品信息"""
        try:
            goods = data.get("goods", data)

            info.title = goods.get("goodsName", "") or goods.get("title", "")

            # 价格（拼多多价格单位为分）
            price_cents = goods.get("minGroupPrice") or goods.get("minNormalPrice") or goods.get("price")
            if price_cents:
                info.price = f"¥{int(price_cents) / 100:.2f}"

            # 图片
            images = goods.get("topGallery") or goods.get("gallery") or goods.get("images", [])
            if isinstance(images, list):
                info.main_images = [img.get("url", img) if isinstance(img, dict) else img for img in images]

            # 描述
            desc = goods.get("goodsDesc") or goods.get("desc", "")
            if desc:
                info.description = self._clean_text(desc)

            # 规格
            specs = goods.get("specs") or goods.get("sku", [])
            if isinstance(specs, list):
                for spec in specs:
                    if isinstance(spec, dict):
                        key = spec.get("specName", "")
                        value = spec.get("specValue", "")
                        if key and value:
                            info.specs[key] = value

        except Exception as e:
            logger.warning(f"[拼多多解析] JSON数据提取失败: {e}")

        return info

    def _parse_from_dom(self, soup: BeautifulSoup, info: ProductInfo) -> ProductInfo:
        """从DOM中提取商品信息（降级方案）"""
        # 标题
        title_el = soup.select_one("[class*='title'], [class*='name'], h1")
        if title_el:
            info.title = self._clean_text(title_el.get_text())

        # 价格
        price_el = soup.select_one("[class*='price'], [class*='Price']")
        if price_el:
            info.price = self._clean_text(price_el.get_text())

        # 图片
        img_elements = soup.select("[class*='gallery'] img, [class*='slider'] img, [class*='main'] img")
        info.main_images = self._extract_image_urls(img_elements)

        return info
