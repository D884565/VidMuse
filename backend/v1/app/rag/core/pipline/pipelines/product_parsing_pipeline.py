import os
from typing import List
from backend.v1.app.rag.core.pipline.base import BasePipeline, BaseProcessor
from backend.v1.app.rag.core.pipline.processors import (
    ProductUnderstandingProcessor,
    ProductGenerateProcessor,
    SchemaValidationProcessor
)


class ProductParsingPipeline(BasePipeline):
    """
    商品解析流水线
    第二条流水线：图文理解 → 商品信息生成 → 结构校验
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None, product_schema_path: str = None):
        """
        初始化商品解析流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param product_schema_path: 商品校验Schema路径，可选
        """
        if product_schema_path is None:
            # 动态构建schema文件路径，适配不同操作系统
            current_dir = os.path.abspath(__file__)
            # 从当前文件向上找到项目根目录（通过查找.git目录或requirements.txt判断）
            project_root = current_dir
            max_depth = 15
            while max_depth > 0:
                # 优先查找项目根目录的标志性文件/目录
                if (os.path.exists(os.path.join(project_root, ".git")) or
                    os.path.exists(os.path.join(project_root, "requirements.txt")) or
                    os.path.exists(os.path.join(project_root, "pyproject.toml"))):
                    # 检查根目录下是否有resources目录
                    if os.path.exists(os.path.join(project_root, "resources")):
                        break
                project_root = os.path.dirname(project_root)
                max_depth -= 1
            if max_depth == 0:
                # 如果没有找到标志性文件，回退到查找最近的resources目录
                project_root = current_dir
                max_depth = 15
                while max_depth > 0 and not os.path.exists(os.path.join(project_root, "resources")):
                    project_root = os.path.dirname(project_root)
                    max_depth -= 1
                if max_depth == 0:
                    raise RuntimeError("Could not find project root directory with resources folder")
            product_schema_path = os.path.join(
                project_root, "resources", "template", "resolve", "valid_template", "product_valid.json"
            )

        if custom_processors:
            processors = custom_processors
        else:
            # 默认处理器顺序
            processors = [
                ProductUnderstandingProcessor(),
                ProductGenerateProcessor(),
                SchemaValidationProcessor(schema_path=product_schema_path)
            ]

        super().__init__(processors)
