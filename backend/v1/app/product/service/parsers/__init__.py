"""商品页面解析器"""
from backend.v1.app.product.service.parsers.base import BaseParser
from backend.v1.app.product.service.parsers.taobao import TaobaoParser
from backend.v1.app.product.service.parsers.jd import JdParser
from backend.v1.app.product.service.parsers.pdd import PddParser
from backend.v1.app.product.service.parsers.douyin import DouyinParser

__all__ = ["BaseParser", "TaobaoParser", "JdParser", "PddParser", "DouyinParser"]
