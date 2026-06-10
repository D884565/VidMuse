import json
from collections.abc import Iterable
from typing import Any


MAX_REFERENCE_IMAGES = 14


def normalize_image_urls(values: Any) -> list[str]:
    # 统一把字符串 / 字典 / 可迭代对象转成 URL 列表，并顺手做去空、去重。
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    if isinstance(values, dict):
        values = values.values()
    if not isinstance(values, Iterable):
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        url = str(value).strip()
        if not url or url in seen:
            continue
        urls.append(url)
        seen.add(url)
    return urls


def extract_reference_images(project: Any) -> list[str]:
    # 参考图优先级：先用户上传，再商品主图，避免后者覆盖用户明确输入。
    images = normalize_image_urls(getattr(project, "reference_images", None))
    seen = set(images)

    product_info = getattr(project, "product_info", None)
    if not product_info:
        return images
    if isinstance(product_info, str):
        try:
            product_info = json.loads(product_info)
        except (TypeError, json.JSONDecodeError):
            return images
    if not isinstance(product_info, dict):
        return images

    product_urls = []
    for key in ("main_images", "main_image_url", "images", "detail_images"):
        product_urls.extend(normalize_image_urls(product_info.get(key)))

    for url in product_urls:
        if url not in seen:
            images.append(url)
            seen.add(url)
    return images


def select_reference_images(
    reference_images: Any = None,
    product_images: Any = None,
    *,
    limit: int = MAX_REFERENCE_IMAGES,
) -> list[str]:
    # 显式参考图优先；只有显式参考图为空时，才回退到商品图。
    selected = normalize_image_urls(reference_images)
    if not selected:
        selected = normalize_image_urls(product_images)
    return selected[:limit]
