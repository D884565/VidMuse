"""
三条流水线使用示例
"""
from unittest.mock import Mock
from backend.v1.app.rag.core.pipline import (
    VideoParsingPipeline,
    ProductParsingPipeline,
    VideoOverallParsingPipeline
)
from backend.v1.app.rag.core.pipline.processors import (
    VideoUnderstandingProcessor,
    ProductUnderstandingProcessor,
    VideoOverallUnderstandingProcessor
)

def example_video_parsing():
    """视频解析流水线示例"""
    print("=" * 60)
    print("📹 视频解析流水线示例")
    print("=" * 60)

    # 使用Mock的LLM客户端
    mock_llm = Mock()
    video_understanding_processor = VideoUnderstandingProcessor(llm_client=mock_llm)

    # 创建流水线
    from backend.v1.app.rag.core.pipline.processors import (
        VideoSplitProcessor,
        SliceGenerateProcessor,
        SchemaValidationProcessor
    )
    pipeline = VideoParsingPipeline(custom_processors=[
        VideoSplitProcessor(),
        video_understanding_processor,
        SliceGenerateProcessor(),
        SchemaValidationProcessor()
    ])

    # 执行流水线
    result = pipeline.run({
        "video_id": "v_001",
        "video_path": "/path/to/your/video.mp4",
        "video_duration": 30000  # 30秒视频
    })

    # 处理结果
    if result["success"]:
        print("✅ 视频解析流水线执行成功！")
        summary = result["data"]["validation_summary"]
        print(f"📊 校验结果：共{summary['total']}个切片，{summary['valid']}个通过，{summary['invalid']}个失败")
        return result["data"]
    else:
        print("❌ 视频解析流水线执行失败！")
        print(f"错误信息：{result['errors']}")
        return None


def example_product_parsing():
    """商品解析流水线示例"""
    print("\n" + "=" * 60)
    print("🛍️  商品解析流水线示例")
    print("=" * 60)

    # 使用Mock的LLM客户端
    mock_llm = Mock()
    product_understanding_processor = ProductUnderstandingProcessor(llm_client=mock_llm)

    # 创建流水线
    from backend.v1.app.rag.core.pipline.processors import (
        ProductGenerateProcessor,
        SchemaValidationProcessor
    )
    pipeline = ProductParsingPipeline(custom_processors=[
        product_understanding_processor,
        ProductGenerateProcessor(),
        SchemaValidationProcessor()  # 自动使用product_valid.json
    ])

    # 执行流水线（图文混合内容示例）
    result = pipeline.run({
        "product_id": "prod_001",
        "multimodal_content": [
            {"type": "text", "text": "这是一款粉色碎花连衣裙，收腰设计，面料舒适，现价159元"},
            {"type": "image_url", "image_url": {"url": "/path/to/product.jpg"}}
        ]
    })

    # 处理结果
    if result["success"]:
        print("✅ 商品解析流水线执行成功！")
        product_data = result["data"]["product_data"]
        print(f"📦 商品名称：{product_data['商品基础信息']['商品名称']}")
        print(f"💰 价格：原价{product_data['价格与服务']['原价']}元，现价{product_data['价格与服务']['现价']}元")
        print(f"📄 生成文件：{result['data']['product_file']}")
        return result["data"]
    else:
        print("❌ 商品解析流水线执行失败！")
        print(f"错误信息：{result['errors']}")
        return None


def example_video_overall_parsing(video_slices_data):
    """视频整体理解流水线示例"""
    print("\n" + "=" * 60)
    print("🎬 视频整体理解流水线示例")
    print("=" * 60)

    if not video_slices_data:
        print("❌ 缺少视频分片数据，请先运行视频解析流水线")
        return

    # 使用Mock的LLM客户端
    mock_llm = Mock()
    video_overall_processor = VideoOverallUnderstandingProcessor(llm_client=mock_llm)

    # 创建流水线
    from backend.v1.app.rag.core.pipline.processors import (
        VideoAggregationProcessor,
        VideoGenerateProcessor,
        SchemaValidationProcessor
    )
    pipeline = VideoOverallParsingPipeline(custom_processors=[
        VideoAggregationProcessor(),
        video_overall_processor,
        VideoGenerateProcessor(),
        SchemaValidationProcessor()  # 自动使用video_valid.json
    ])

    # 执行流水线（输入为视频解析流水线的输出结果）
    result = pipeline.run({
        "video_id": "v_001",
        "video_duration": 30000,
        "valid_slices": video_slices_data["valid_slices"]  # 传入校验通过的切片
    })

    # 处理结果
    if result["success"]:
        print("✅ 视频整体理解流水线执行成功！")
        video_data = result["data"]["video_data"]
        print(f"🎥 视频ID：{video_data['视频基本信息']['video_id']}")
        print(f"📦 推广商品：{video_data['视频基本信息']['商品名称']}")
        print(f"🎯 目标人群：{video_data['视频基本信息']['目标人群']}")
        print(f"📄 生成文件：{result['data']['video_file']}")
        return result["data"]
    else:
        print("❌ 视频整体理解流水线执行失败！")
        print(f"错误信息：{result['errors']}")
        return None

def main():
    """主函数：运行所有示例"""
    # 1. 运行视频解析流水线
    video_data = example_video_parsing()

    # 2. 运行商品解析流水线
    product_data = example_product_parsing()

    # 3. 运行视频整体理解流水线
    if video_data:
        overall_data = example_video_overall_parsing(video_data)

    print("\n" + "=" * 60)
    print("🎉 所有流水线示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
