"""Prompt模板工具"""
import os
from typing import Dict, Any
from string import Template

class PromptTemplate:
    """Prompt模板管理器，支持从文件加载和变量渲染"""

    def __init__(self, template_dir: str):
        self.template_dir = template_dir
        self._templates: Dict[str, Template] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """加载所有模板文件"""
        for root, _, files in os.walk(self.template_dir):
            for file in files:
                if file.endswith(".txt") or file.endswith(".prompt"):
                    file_path = os.path.join(root, file)
                    template_name = os.path.relpath(file_path, self.template_dir)
                    template_name = os.path.splitext(template_name)[0]

                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        self._templates[template_name] = Template(content)

    def render(self, template_name: str, **kwargs) -> str:
        """渲染模板"""
        if template_name not in self._templates:
            raise ValueError(f"模板 {template_name} 不存在")

        template = self._templates[template_name]
        return template.safe_substitute(**kwargs)

    def has_template(self, template_name: str) -> bool:
        """检查模板是否存在"""
        return template_name in self._templates

    def list_templates(self) -> list:
        """获取所有模板名称"""
        return list(self._templates.keys())
