import json
from typing import Any, Union, List, Dict


class JsonFlattener:
    """
    JSON展开工具类，将JSON结构转换为易读的自然语言字符串，去除JSON语法符号。

    功能：
    - 支持输入JSON字符串、Python字典、Python列表
    - 递归展开嵌套结构
    - 去除双引号、大括号、逗号等JSON语法符号
    - 保留数组结构，用[]包裹
    - 键值对用中文冒号"："连接
    - 不同字段之间用空格分隔

    示例：
    输入：{"姓名": "张三", "详细信息": [{"住址": "北京市", "父亲": "李四"}]}
    输出：姓名：张三 详细信息：[住址：北京市，父亲：李四]
    """

    @classmethod
    def flatten(cls, data: Union[str, Dict, List]) -> str:
        """
        展开JSON数据为字符串

        Args:
            data: 输入数据，可以是JSON字符串、字典或列表

        Returns:
            展开后的字符串
        """
        # 如果是字符串，先解析为JSON对象
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                # 如果不是合法JSON，直接返回原字符串
                return data

        # 顶层字典用空格分隔键值对
        if isinstance(data, dict):
            return cls._process_dict(data, separator=" ")
        else:
            return cls._process_value(data)

    @classmethod
    def _process_value(cls, value: Any, current_key: str = "") -> str:
        """
        递归处理不同类型的值

        Args:
            value: 要处理的值
            current_key: 当前键名，用于嵌套结构

        Returns:
            处理后的字符串
        """
        if isinstance(value, dict):
            # 嵌套字典用中文逗号分隔键值对
            dict_content = cls._process_dict(value, separator="，")
            if current_key:
                return f"{current_key}：{dict_content}"
            else:
                return dict_content
        elif isinstance(value, list):
            list_content = cls._process_list(value)
            if current_key:
                return f"{current_key}：{list_content}"
            else:
                return list_content
        else:
            # 基本类型
            value_str = cls._escape_special_chars(str(value))
            if current_key:
                return f"{current_key}：{value_str}"
            else:
                return value_str

    @classmethod
    def _process_dict(cls, d: Dict, separator: str = "，") -> str:
        """
        处理字典类型

        Args:
            d: 字典对象
            separator: 键值对之间的分隔符，默认中文逗号

        Returns:
            处理后的字符串
        """
        items = []
        for key, value in d.items():
            processed_key = cls._escape_special_chars(str(key))
            processed_value = cls._process_value(value, processed_key)
            items.append(processed_value)

        # 用指定分隔符分隔不同的键值对
        return separator.join(items)

    @classmethod
    def _process_list(cls, lst: List) -> str:
        """
        处理列表类型

        Args:
            lst: 列表对象

        Returns:
            处理后的字符串，用[]包裹
        """
        items = []
        for item in lst:
            processed_item = cls._process_value(item)
            items.append(processed_item)

        # 列表内容用中文逗号分隔，外面包裹[]
        list_content = "，".join(items)
        return f"[{list_content}]"

    @staticmethod
    def _escape_special_chars(s: str) -> str:
        """
        转义特殊字符，去除JSON语法符号

        Args:
            s: 输入字符串

        Returns:
            处理后的字符串
        """
        # 去除双引号、大括号、中括号、逗号等JSON符号
        chars_to_remove = ['"', '{', '}', ',', '\n', '\r', '\t']
        for char in chars_to_remove:
            s = s.replace(char, "")

        # 去除多余的空格
        s = " ".join(s.split())

        return s
