"""商品信息抓取服务"""
import json
import logging
import os
import re
from urllib.parse import urlparse

from backend.v1.app.product.dao.product_info import ProductInfo
from backend.v1.app.product.service.parsers import (
    TaobaoParser, JdParser, PddParser, DouyinParser
)
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)

# Cookie 配置文件路径
COOKIE_DIR = os.path.join(os.path.dirname(__file__), "cookies")

# 平台域名映射
PLATFORM_DOMAINS = {
    "taobao": ["item.taobao.com", "detail.tmall.com", "tmall.com"],
    "jd": ["item.jd.com", "jd.com"],
    "pdd": ["mobile.yangkeduo.com", "pinduoduo.com"],
    "douyin": ["haohuo.jinritemai.com", "jinritemai.com"],
}

# 平台解析器映射
PARSERS = {
    "taobao": TaobaoParser,
    "jd": JdParser,
    "pdd": PddParser,
    "douyin": DouyinParser,
}


class ProductCrawlService:
    """商品信息抓取服务"""

    def __init__(self):
        os.makedirs(COOKIE_DIR, exist_ok=True)

    def _load_cookies(self, platform: str) -> list[dict]:
        """
        加载平台 Cookie。

        优先级：
        1. 环境变量 TAOBAO_COOKIES / JD_COOKIES 等（JSON 字符串）
        2. cookies/{platform}.json 文件

        :param platform: 平台标识
        :returns: Cookie 列表
        """
        # 1. 从环境变量读取
        env_key = f"{platform.upper()}_COOKIES"
        env_value = os.environ.get(env_key)
        if env_value:
            try:
                return json.loads(env_value)
            except json.JSONDecodeError:
                logger.warning(f"[Cookie] 环境变量 {env_key} 格式错误")

        # 2. 从文件读取
        cookie_file = os.path.join(COOKIE_DIR, f"{platform}.json")
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"[Cookie] 读取 {cookie_file} 失败: {e}")

        return []

    def detect_platform(self, url: str) -> str | None:
        """
        根据URL识别电商平台。

        :param url: 商品URL
        :returns: 平台标识（taobao/jd/pdd/douyin），无法识别返回None
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""

            for platform, domains in PLATFORM_DOMAINS.items():
                for domain in domains:
                    if domain in hostname:
                        return platform
        except Exception:
            pass

        return None

    async def crawl(self, url: str) -> ProductInfo:
        """
        抓取商品信息主流程。

        :param url: 商品URL
        :returns: ProductInfo 结构化数据
        """
        # 1. 检测平台
        platform = self.detect_platform(url)
        if not platform:
            logger.warning(f"[商品抓取] 不支持的平台: {url}")
            return ProductInfo(url=url)

        # 2. 获取解析器
        parser_cls = PARSERS.get(platform)
        if not parser_cls:
            logger.warning(f"[商品抓取] 未找到解析器: {platform}")
            return ProductInfo(platform=platform, url=url)

        # 3. 渲染页面并解析
        try:
            cookies = self._load_cookies(platform)
            html = await self._render_page(url, cookies=cookies)
            parser = parser_cls()
            info = parser.parse(html, url)
            logger.info(f"[商品抓取] 成功: {info.title}")
            return info
        except Exception as e:
            logger.error(f"[商品抓取] 失败: {e}")
            return ProductInfo(platform=platform, url=url)

    async def _render_page(self, url: str, timeout: int = 30000, cookies: list[dict] = None) -> str:
        """
        使用 Playwright 渲染页面。

        :param url: 页面URL
        :param timeout: 超时时间（毫秒）
        :param cookies: Cookie 列表
        :returns: 渲染后的HTML
        :raises: 超时或渲染失败时抛出异常
        """
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                # 注入 Cookie
                if cookies:
                    await context.add_cookies(cookies)
                    logger.info(f"[Cookie] 已注入 {len(cookies)} 个 Cookie")

                page = await context.new_page()

                # 访问页面
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

                # 等待页面加载
                await page.wait_for_timeout(2000)

                # 滚动页面触发懒加载（图片通常是懒加载的）
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
                await page.wait_for_timeout(1000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 2 / 3)")
                await page.wait_for_timeout(1000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

                # 回到顶部获取完整HTML
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(500)

                # 获取渲染后的HTML
                html = await page.content()
                return html

            finally:
                await browser.close()

    async def upload_product_images(
        self,
        product_info: ProductInfo,
        project_id: int,
    ) -> dict[str, list[str]]:
        """
        上传商品图片到TOS。

        :param product_info: 商品信息
        :param project_id: 项目ID
        :returns: 上传后的图片URL字典 {"main": [...], "detail": [...]}
        """
        import io
        import requests

        result = {"main": [], "detail": []}

        # 上传主图
        for i, img_url in enumerate(product_info.main_images[:5]):  # 最多5张主图
            try:
                object_key = f"projects/{project_id}/product_main_{i}.jpg"
                # 下载图片并上传
                response = requests.get(img_url, timeout=10)
                response.raise_for_status()

                # 上传到TOS
                url = get_storage_client().upload_fileobj(io.BytesIO(response.content), object_key)
                result["main"].append(url)
            except Exception as e:
                logger.warning(f"[图片上传] 主图上传失败: {e}")

        # 上传详情图
        for i, img_url in enumerate(product_info.detail_images[:10]):  # 最多10张详情图
            try:
                object_key = f"projects/{project_id}/product_detail_{i}.jpg"
                response = requests.get(img_url, timeout=10)
                response.raise_for_status()

                url = get_storage_client().upload_fileobj(io.BytesIO(response.content), object_key)
                result["detail"].append(url)
            except Exception as e:
                logger.warning(f"[图片上传] 详情图上传失败: {e}")

        return result

    def format_product_info_for_prompt(self, product_info: ProductInfo) -> str:
        """
        将商品信息格式化为LLM prompt可用的文本。

        :param product_info: 商品信息
        :returns: 格式化后的文本
        """
        if product_info.is_empty:
            return ""

        parts = []
        if product_info.title:
            parts.append(f"- 商品名称：{product_info.title}")
        if product_info.price:
            parts.append(f"- 价格：{product_info.price}")
        if product_info.description:
            parts.append(f"- 商品描述：{product_info.description}")
        if product_info.specs:
            specs_text = "、".join(f"{k}:{v}" for k, v in product_info.specs.items())
            parts.append(f"- 规格参数：{specs_text}")

        return "\n".join(parts)


# 单例
product_crawl_service = ProductCrawlService()
