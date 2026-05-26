"""淘宝/天猫商品页面解析器"""
import json
import logging
import re

from bs4 import BeautifulSoup

from backend.v1.app.product.dao.product_info import ProductInfo
from backend.v1.app.product.service.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class TaobaoParser(BaseParser):
    """淘宝/天猫商品页面解析器"""

    def parse(self, html: str, url: str) -> ProductInfo:
        soup = BeautifulSoup(html, "html.parser")
        info = ProductInfo(platform="taobao", url=url)

        try:
            # 标题
            title_el = soup.select_one("h1, .tb-main-title, [data-title]")
            if title_el:
                info.title = self._clean_text(title_el.get_text())

            # 尝试从页面脚本中提取JSON数据
            script_data = self._extract_json_data(soup)
            if script_data:
                info = self._parse_json_data(info, script_data)
            else:
                # 降级：从DOM提取
                info = self._parse_from_dom(soup, info)

        except Exception as e:
            logger.warning(f"[淘宝解析] 解析失败: {e}")

        return info

    def _extract_json_data(self, soup: BeautifulSoup) -> dict | None:
        """从页面脚本中提取商品JSON数据"""
        # 淘宝/天猫页面通常在脚本中嵌入商品数据
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            # 查找 g_page_config 或类似的数据结构
            if "g_page_config" in text:
                try:
                    match = re.search(r'g_page_config\s*=\s*({.*?});', text, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))
                except (json.JSONDecodeError, AttributeError):
                    pass

            # 查找 __INITIAL_DATA__ 或类似结构
            if "__INITIAL_DATA__" in text:
                try:
                    match = re.search(r'__INITIAL_DATA__\s*=\s*({.*?});', text, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))
                except (json.JSONDecodeError, AttributeError):
                    pass

        return None

    def _parse_json_data(self, info: ProductInfo, data: dict) -> ProductInfo:
        """从JSON数据中提取商品信息"""
        try:
            # 尝试递归查找商品信息
            item_info = self._find_key(data, "itemInfoModel") or self._find_key(data, "item")

            if item_info:
                info.title = item_info.get("title", info.title)

                # 价格
                price_info = item_info.get("price") or item_info.get("priceInfo")
                if isinstance(price_info, dict):
                    info.price = str(price_info.get("price", ""))
                elif isinstance(price_info, str):
                    info.price = price_info

                # 图片
                images = item_info.get("images") or item_info.get("picsPath", [])
                if isinstance(images, list):
                    info.main_images = [img for img in images if isinstance(img, str) and img.startswith("http")]

            # 描述
            desc = self._find_key(data, "desc") or self._find_key(data, "description")
            if isinstance(desc, str):
                info.description = self._clean_text(desc)

        except Exception as e:
            logger.warning(f"[淘宝解析] JSON数据提取失败: {e}")

        return info

    def _parse_from_dom(self, soup: BeautifulSoup, info: ProductInfo) -> ProductInfo:
        """从DOM中提取商品信息（降级方案）"""
        # 价格
        price_el = soup.select_one(".tb-rmb-num, .tm-price, [class*='price']")
        if price_el:
            info.price = self._clean_text(price_el.get_text())

        # 主图
        img_elements = soup.select("#J_ImgBooth, .tb-thumb img, [class*='main-img'] img")
        info.main_images = self._extract_image_urls(img_elements)

        # 描述
        desc_el = soup.select_one("#description, .tb-desc, [class*='desc']")
        if desc_el:
            info.description = self._clean_text(desc_el.get_text())

        return info

    def _find_key(self, data: dict, key: str):
        """递归查找字典中的key"""
        if key in data:
            return data[key]
        for v in data.values():
            if isinstance(v, dict):
                result = self._find_key(v, key)
                if result is not None:
                    return result
        return None
