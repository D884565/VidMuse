"""商品分类匹配服务
将大模型输出的分类文本自动匹配到product_categories表中的分类记录
支持多级匹配策略：精确匹配 > 路径匹配 > 模糊匹配
"""
import re
import logging
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from backend.store.database.sync_database import get_db
from backend.v1.app.product.dao.product_category_dao import ProductCategoryDAO
from backend.v1.app.models.product_category import ProductCategory
logger = logging.getLogger(__name__)
class ProductCategoryMatcher:
    """商品分类匹配器"""

    # 单例实例
    _instance = None
    # 分类数据缓存
    _categories: List[ProductCategory] = []
    # 索引：分类名称 -> 分类列表（可能重名）
    _name_index: Dict[str, List[ProductCategory]] = {}
    # 索引：分类路径 -> 分类（路径唯一）
    _path_index: Dict[str, ProductCategory] = {}
    # 索引：三级分类名称 -> 分类列表（优先匹配三级分类）
    _level3_name_index: Dict[str, List[ProductCategory]] = {}
    # 同义词词典
    _synonyms: Dict[str, List[str]] = {
        "手机": ["移动电话", "智能手机", "电话"],
        "电脑": ["计算机", "笔记本", "笔记本电脑", "PC"],
        "电视": ["电视机", "平板电视", "智能电视"],
        "冰箱": ["电冰箱", "冰柜"],
        "洗衣机": ["干洗机", "滚筒洗衣机", "波轮洗衣机"],
        "空调": ["空调器", "冷气机", "暖气"],
        "耳机": ["耳麦", "头戴式耳机", "蓝牙耳机"],
        "手表": ["腕表", "智能手表"],
        "相机": ["照相机", "数码相机", "单反相机"],
        "平板": ["平板电脑", "iPad"],
    }

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reload()
        return cls._instance

    def __init__(self):
        """初始化，确保数据已加载"""
        if not self._categories:
            self.reload()

    def reload(self) -> None:
        """重新加载分类数据，构建索引"""
        logger.info("开始加载商品分类数据...")
        try:
            db: Session = next(get_db())
            self._categories = ProductCategoryDAO.list_all_categories(db)
            self._build_indexes()
            logger.info(f"商品分类数据加载完成，共加载 {len(self._categories)} 条分类记录")
        except Exception as e:
            logger.error(f"加载商品分类数据失败: {str(e)}", exc_info=True)
        finally:
            if 'db' in locals() and db:
                db.close()

    def _build_indexes(self) -> None:
        """构建分类索引"""
        self._name_index.clear()
        self._path_index.clear()
        self._level3_name_index.clear()

        for category in self._categories:
            # 构建名称索引
            if category.name not in self._name_index:
                self._name_index[category.name] = []
            self._name_index[category.name].append(category)

            # 构建路径索引（路径格式：/1/2/3/）
            self._path_index[category.path] = category

            # 构建三级分类名称索引
            if category.level == 3:
                if category.name not in self._level3_name_index:
                    self._level3_name_index[category.name] = []
                self._level3_name_index[category.name].append(category)

    def _parse_category_levels(self, category_text: str) -> List[str]:
        """
        解析分类文本，提取各级分类名称
        支持分隔符：>、/、|、空格、中文顿号、中文逗号
        :param category_text: 原始分类文本
        :return: 各级分类名称列表
        """
        if not category_text:
            return []

        # 统一替换分隔符为>
        text = re.sub(r'[\\/|、，\s]+', '>', category_text.strip())
        # 分割并过滤空字符串
        levels = [level.strip() for level in text.split('>') if level.strip()]

        # 同义词扩展
        expanded_levels = []
        for level in levels:
            expanded = [level]
            # 查找同义词
            for syn, equivalents in self._synonyms.items():
                if level in equivalents:
                    expanded.append(syn)
                elif level == syn:
                    expanded.extend(equivalents)
            expanded_levels.extend(expanded)

        # 去重并保持顺序
        seen = set()
        return [x for x in expanded_levels if not (x in seen or seen.add(x))]

    def _exact_match(self, category_name: str) -> Optional[ProductCategory]:
        """
        精确匹配分类名称（优先匹配三级分类）
        :param category_name: 分类名称
        :return: 匹配到的分类，未找到返回None
        """
        # 优先匹配三级分类
        if category_name in self._level3_name_index:
            # 如果有多个重名的三级分类，返回第一个（通常分类名称应该唯一）
            return self._level3_name_index[category_name][0]

        # 匹配所有层级的分类
        if category_name in self._name_index:
            return self._name_index[category_name][0]

        return None

    def _path_match(self, levels: List[str]) -> Optional[ProductCategory]:
        """
        路径匹配，支持部分路径匹配
        :param levels: 分类层级列表
        :return: 匹配到的分类，未找到返回None
        """
        if not levels:
            return None

        # 尝试完全匹配路径（从最后往前匹配）
        for i in range(len(levels)):
            sub_path = '>'.join(levels[i:])
            # 查找所有分类的名称路径是否包含该子路径
            for category in self._categories:
                # 构建分类的名称路径（如：家用电器>厨房小电>电饭煲）
                category_name_path = self._get_category_name_path(category)
                if sub_path in category_name_path:
                    return category

        return None

    def _get_category_name_path(self, category: ProductCategory) -> str:
        """
        获取分类的名称路径，如：家用电器>厨房小电>电饭煲
        :param category: 分类对象
        :return: 分类名称路径
        """
        # 解析分类路径中的ID，获取各级分类名称
        path_ids = [int(id_str) for id_str in category.path.strip('/').split('/') if id_str]
        name_parts = []

        for path_id in path_ids:
            for cat in self._categories:
                if cat.id == path_id:
                    name_parts.append(cat.name)
                    break

        return '>'.join(name_parts)

    def _fuzzy_match(self, category_name: str, threshold: float = 0.7) -> Optional[ProductCategory]:
        """
        模糊匹配，使用编辑距离计算相似度
        :param category_name: 分类名称
        :param threshold: 相似度阈值，0-1之间，越高越严格
        :return: 匹配到的分类，未找到返回None
        """
        best_match = None
        highest_similarity = 0.0

        # 优先在三级分类中模糊匹配
        for name, categories in self._level3_name_index.items():
            similarity = SequenceMatcher(None, category_name, name).ratio()
            if similarity > highest_similarity and similarity >= threshold:
                highest_similarity = similarity
                best_match = categories[0]

        # 如果三级分类没有匹配到，在所有分类中查找
        if not best_match:
            for name, categories in self._name_index.items():
                similarity = SequenceMatcher(None, category_name, name).ratio()
                if similarity > highest_similarity and similarity >= threshold:
                    highest_similarity = similarity
                    best_match = categories[0]

        if best_match:
            logger.debug(f"模糊匹配成功: '{category_name}' -> '{best_match.name}', 相似度: {highest_similarity:.2f}")

        return best_match

    def match(self, category_text: str) -> Optional[Dict]:
        """
        匹配商品分类
        :param category_text: 大模型输出的分类文本，支持多种格式
        :return: 匹配结果字典，包含id, name, path, level等字段，未匹配到返回None
        """
        if not category_text or not self._categories:
            return None

        try:
            levels = self._parse_category_levels(category_text)
            if not levels:
                return None

            logger.debug(f"解析分类文本 '{category_text}' 得到层级: {levels}")

            # 1. 优先精确匹配最后一级分类（三级分类）
            for level in reversed(levels):
                exact_match = self._exact_match(level)
                if exact_match:
                    logger.debug(f"精确匹配成功: '{category_text}' -> '{exact_match.name}' (ID: {exact_match.id})")
                    return self._format_result(exact_match)

            # 2. 路径匹配
            path_match = self._path_match(levels)
            if path_match:
                logger.debug(f"路径匹配成功: '{category_text}' -> '{path_match.name}' (ID: {path_match.id})")
                return self._format_result(path_match)

            # 3. 模糊匹配
            for level in reversed(levels):
                fuzzy_match = self._fuzzy_match(level)
                if fuzzy_match:
                    logger.debug(f"模糊匹配成功: '{category_text}' -> '{fuzzy_match.name}' (ID: {fuzzy_match.id})")
                    return self._format_result(fuzzy_match)

            # 4. 尝试匹配整个文本
            fuzzy_match = self._fuzzy_match(category_text)
            if fuzzy_match:
                logger.debug(f"模糊匹配成功: '{category_text}' -> '{fuzzy_match.name}' (ID: {fuzzy_match.id})")
                return self._format_result(fuzzy_match)

            logger.warning(f"分类匹配失败: '{category_text}'")
            return None

        except Exception as e:
            logger.error(f"分类匹配过程发生错误: {str(e)}", exc_info=True)
            return None

    def _format_result(self, category: ProductCategory) -> Dict:
        """格式化匹配结果"""
        return {
            "id": category.id,
            "name": category.name,
            "parent_id": category.parent_id,
            "level": category.level,
            "path": category.path,
            "name_path": self._get_category_name_path(category)
        }

    def get_category_by_id(self, category_id: int) -> Optional[Dict]:
        """根据分类ID获取分类信息"""
        for category in self._categories:
            if category.id == category_id:
                return self._format_result(category)
        return None

    def get_all_categories(self) -> List[Dict]:
        """获取所有分类信息"""
        return [self._format_result(cat) for cat in self._categories]
