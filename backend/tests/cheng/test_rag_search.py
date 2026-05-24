"""
RAG搜索功能测试类
注意：运行前请确保已在 .env 文件中配置正确的 LLM 和向量数据库参数
"""
import os
import pytest
from dotenv import load_dotenv
from typing import List, Dict, Any

# 加载环境变量
load_dotenv()

from backend.v1.app.rag.core import search
from backend.providers.dto.schema import (
    TextContent,
    ImageUrlContent,
    VideoUrlContent
)
from backend.framework.exceptions.exceptions import BaseAppException


class TestRAGSearch:
    """RAG搜索功能测试类"""

    def setup_method(self):
        """测试前的准备工作"""
        # 测试用的查询内容
        self.text_query = "美丽的自然风光"
        self.image_query = ImageUrlContent(
            image_url={"url": "https://picsum.photos/200/300"}
        )
        self.video_query = VideoUrlContent(
            video_url={"url": "https://example.com/test_video.mp4"}
        )

    def test_text_search_with_rerank(self):
        """测试纯文本搜索（启用重排序）"""
        try:
            result = search(
                query=self.text_query,
                top_k=5,
                rerank=True
            )

            print(result)

            # 验证返回结果结构
            assert "query" in result
            assert "results" in result
            assert "embedding_usage" in result
            assert "rerank_enabled" in result
            assert result["rerank_enabled"] is True
            assert "rerank_usage" in result

            # 验证结果数量
            assert len(result["results"]) <= 5

            # 验证每个结果的字段
            for item in result["results"]:
                assert "id" in item
                assert "document" in item
                assert "metadata" in item
                assert "score" in item
                assert "rerank_rank" in item
                assert 0 <= item["score"] <= 1  # 相似度分数在0-1之间

            print("✅ 纯文本搜索（启用重排序）测试通过")

        except Exception as e:
            pytest.fail(f"纯文本搜索测试失败: {str(e)}")

    def test_text_search_without_rerank(self):
        """测试纯文本搜索（禁用重排序）"""
        try:
            result = search(
                query=self.text_query,
                top_k=5,
                rerank=False
            )

            # 验证返回结果结构
            assert result["rerank_enabled"] is False
            assert result["rerank_usage"] is None

            # 验证结果中没有rerank_rank字段
            for item in result["results"]:
                assert "rerank_rank" not in item

            print("✅ 纯文本搜索（禁用重排序）测试通过")

        except Exception as e:
            pytest.fail(f"纯文本搜索（禁用重排序）测试失败: {str(e)}")

    def test_image_search(self):
        """测试图片搜索"""
        try:
            result = search(
                query=self.image_query,
                top_k=3,
                rerank=True
            )

            assert len(result["results"]) <= 3
            assert result["rerank_enabled"] is True

            print("✅ 图片搜索测试通过")

        except Exception as e:
            pytest.fail(f"图片搜索测试失败: {str(e)}")

    def test_multimodal_search(self):
        """测试多模态组合搜索（文本+图片）"""
        try:
            query = [
                TextContent(text="山川河流"),
                self.image_query
            ]

            result = search(
                query=query,
                top_k=5,
                rerank=True
            )

            assert len(result["results"]) <= 5
            print("✅ 多模态组合搜索测试通过")

        except Exception as e:
            pytest.fail(f"多模态组合搜索测试失败: {str(e)}")

    def test_search_with_filter(self):
        """测试带过滤条件的搜索"""
        try:
            # 过滤条件：只搜索图片类型
            filter_condition = {"type": "image"}

            result = search(
                query=self.text_query,
                top_k=5,
                where=filter_condition,
                rerank=False
            )

            # 验证返回的结果都符合过滤条件（如果有结果的话）
            for item in result["results"]:
                metadata = item.get("metadata", {})
                if "type" in metadata:
                    assert metadata["type"] == "image"

            print("✅ 带过滤条件的搜索测试通过")

        except Exception as e:
            pytest.fail(f"带过滤条件的搜索测试失败: {str(e)}")

    def test_invalid_top_k(self):
        """测试无效的top_k参数"""
        # 测试top_k小于1
        with pytest.raises(BaseAppException) as excinfo:
            search(query=self.text_query, top_k=0)
        assert "top_k必须在1-100之间" in str(excinfo.value)

        # 测试top_k大于100
        with pytest.raises(BaseAppException) as excinfo:
            search(query=self.text_query, top_k=200)
        assert "top_k必须在1-100之间" in str(excinfo.value)

        print("✅ 无效top_k参数验证测试通过")

    def test_invalid_query_format(self):
        """测试无效的查询格式"""
        # 测试无效的查询类型
        with pytest.raises(BaseAppException) as excinfo:
            search(query=12345)  # 数字类型，无效
        assert "不支持的查询内容格式" in str(excinfo.value)

        # 测试混合类型的列表
        with pytest.raises(BaseAppException) as excinfo:
            search(query=[TextContent(text="test"), "invalid string"])  # 列表中包含无效类型
        assert "不支持的查询内容格式" in str(excinfo.value)

        print("✅ 无效查询格式验证测试通过")

    def test_empty_query_list(self):
        """测试空的查询列表"""
        with pytest.raises(BaseAppException) as excinfo:
            search(query=[])
        assert "不支持的查询内容格式" in str(excinfo.value)

        print("✅ 空查询列表验证测试通过")


if __name__ == "__main__":
    # 运行所有测试
    test = TestRAGSearch()
    test.setup_method()

    print("\n开始运行RAG搜索功能测试...\n")

    try:
        test.test_text_search_with_rerank()
        test.test_text_search_without_rerank()
        test.test_image_search()
        test.test_multimodal_search()
        test.test_search_with_filter()
        test.test_invalid_top_k()
        test.test_invalid_query_format()
        test.test_empty_query_list()

        print("\n🎉 所有RAG搜索功能测试通过！")
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
