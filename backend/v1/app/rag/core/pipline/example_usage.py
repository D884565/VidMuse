"""
三条流水线使用示例
"""
import os
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
    """视频解析流水线示例（端到端整合版）"""
    print("=" * 60)
    print("视频解析流水线示例（端到端整合版）")
    print("=" * 60)

    # 使用Mock的LLM客户端
    mock_llm = Mock()
    video_understanding_processor = VideoUnderstandingProcessor(llm_client=mock_llm)
    video_overall_processor = VideoOverallUnderstandingProcessor(llm_client=mock_llm)

    # 创建自定义处理器链（如果不自定义则使用默认的完整端到端流程）
    from backend.v1.app.rag.core.pipline.processors import (
        VideoSplitProcessor,
        SchemaValidationProcessor,
        VideoAggregationProcessor,
        VideoGenerateProcessor
    )

    # 手动获取schema路径
    current_dir = os.path.abspath(__file__)
    project_root = current_dir
    while not os.path.exists(os.path.join(project_root, "resources")):
        project_root = os.path.dirname(project_root)

    slice_schema = os.path.join(project_root, "resources", "template", "resolve", "valid_template", "slice_valid.json")
    video_schema = os.path.join(project_root, "resources", "template", "resolve", "valid_template", "video_valid.json")

    pipeline = VideoParsingPipeline(custom_processors=[
        VideoSplitProcessor(slice_duration=5000),
        video_understanding_processor,
        SliceGenerateProcessor(),
        SchemaValidationProcessor(
            schema_path=slice_schema,
            data_key="slice_data",
            valid_key="valid_slices",
            invalid_key="invalid_slices",
            summary_key="slice_validation_summary",
            id_field="slice_id"
        ),
        VideoAggregationProcessor(),
        video_overall_processor,
        VideoGenerateProcessor(),
        SchemaValidationProcessor(
            schema_path=video_schema,
            data_key="video_data",
            valid_key="valid_video",
            invalid_key="invalid_video",
            summary_key="video_validation_summary",
            id_field="video_id"
        )
    ])

    # 也可以直接使用默认流水线，不需要自定义处理器：
    # pipeline = VideoParsingPipeline()

    # 执行流水线
    result = pipeline.run({
        "video_id": "v_001",
        "video_path": "/path/to/your/video.mp4",
        "video_duration": 30000  # 30秒视频
    })

    # 处理结果
    if result["success"]:
        print("视频解析流水线执行成功！")
        slice_summary = result["data"]["slice_validation_summary"]
        print(f"分片校验结果：共{slice_summary['total']}个切片，{slice_summary['valid']}个通过，{slice_summary['invalid']}个失败")

        if "video_validation_summary" in result["data"]:
            video_summary = result["data"]["video_validation_summary"]
            print(f"整体校验结果：共{video_summary['total']}个视频，{video_summary['valid']}个通过，{video_summary['invalid']}个失败")

        if result["data"]["valid_slices"]:
            print("\n通过校验的切片：")
            for i, slice_data in enumerate(result["data"]["valid_slices"][:3]):  # 显示前3个
                print(f"  - {slice_data['slice_id']}: {slice_data['单片段模板']['模板名称']}")
            if len(result["data"]["valid_slices"]) > 3:
                print(f"  ... 共{len(result['data']['valid_slices'])}个切片")

        if result["data"]["invalid_slices"]:
            print("\n校验失败的切片：")
            for invalid in result["data"]["invalid_slices"]:
                print(f"  - {invalid['slice_id']}: {invalid['error']}")

        if result["data"].get("valid_video"):
            print("\n整体视频分析结果：")
            video_data = result["data"]["valid_video"][0]
            print(f"  商品名称：{video_data['视频基本信息']['商品名称']}")
            print(f"  目标人群：{video_data['视频基本信息']['目标人群']}")
            print(f"  分片数量：{len(video_data['片段索引列表'])}个")
            print(f"  视频数据已生成并保存在上下文，无本地文件")

        print(f"\n分片数据已生成，共{len(result['data'].get('valid_slices', []))}个通过校验")

        return result["data"]
    else:
        print("视频解析流水线执行失败！")
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
        print("商品解析流水线执行成功！")
        product_summary = result["data"]["product_validation_summary"]
        print(f"校验结果：共{product_summary['total']}个商品，{product_summary['valid']}个通过，{product_summary['invalid']}个失败")

        product_data = result["data"]["product_data"]
        print(f"\n商品信息：")
        print(f"  商品名称：{product_data['商品基础信息']['商品名称']}")
        print(f"  价格：原价{product_data['价格与服务']['原价']}元，现价{product_data['价格与服务']['现价']}元")
        print(f"  商品数据已生成并保存在上下文，无本地文件")

        return result["data"]
    else:
        print("商品解析流水线执行失败！")
        print(f"错误信息：{result['errors']}")
        return None


def example_video_overall_parsing(video_slices_data):
    """视频整体理解流水线示例（独立使用版）"""
    print("\n" + "=" * 60)
    print("🎬 视频整体理解流水线示例（独立使用版）")
    print("=" * 60)

    if not video_slices_data:
        print("缺少视频分片数据，请先运行视频解析流水线")
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
        print("视频整体理解流水线执行成功！")
        video_summary = result["data"]["video_validation_summary"]
        print(f"校验结果：共{video_summary['total']}个视频，{video_summary['valid']}个通过，{video_summary['invalid']}个失败")

        video_data = result["data"]["video_data"]
        print(f"\n视频信息：")
        print(f"  视频ID：{video_data['视频基本信息']['video_id']}")
        print(f"  推广商品：{video_data['视频基本信息']['商品名称']}")
        print(f"  目标人群：{video_data['视频基本信息']['目标人群']}")
        print(f"  生成文件：{result['data']['video_file']}")

        # 清理测试文件
        if os.path.exists(result["data"]["video_file"]):
            os.remove(result["data"]["video_file"])

        return result["data"]
    else:
        print("视频整体理解流水线执行失败！")
        print(f"错误信息：{result['errors']}")
        return None


def example_persistence_and_resume():
    """流水线持久化和断点续跑示例"""
    print("\n" + "=" * 60)
    print("💾 流水线持久化和断点续跑示例")
    print("=" * 60)

    from backend.v1.app.rag.core.pipline import PipelineExecutionDAO, PipelineExecutionStatus

    # 创建流水线（默认开启持久化）
    pipeline = VideoParsingPipeline(
        enable_persistence=True,
        persist_after_each_processor=True
    )

    # 第一次执行（模拟执行到一半失败）
    print("\n1. 第一次执行流水线（模拟中途失败）...")
    result = pipeline.run_with_persistence({
        "video_id": "v_test_001",
        "video_path": "/path/to/test/video.mp4",
        "video_duration": 30000
    })

    if not result["success"]:
        execution_id = result["execution_id"]
        print(f"   执行失败，execution_id: {execution_id}")
        print(f"   错误信息: {result['errors'][0]}")

        # 查询执行状态
        status = pipeline.get_execution_status(execution_id)
        if status:
            print(f"\n2. 查询执行状态:")
            print(f"   状态: {status['status']}")
            print(f"   执行到处理器索引: {status['current_processor_index']}/{status['total_processors']}")

            # 修复问题后，从断点恢复执行
            print("\n3. 从断点恢复执行...")
            resume_result = pipeline.resume_execution(execution_id)

            if resume_result["success"]:
                print("   恢复执行成功！")
                slice_summary = resume_result["data"]["slice_validation_summary"]
                print(f"   分片校验结果：共{slice_summary['total']}个切片，{slice_summary['valid']}个通过，{slice_summary['invalid']}个失败")
            else:
                print(f"   恢复执行失败: {resume_result['errors']}")

    # 演示关闭持久化的执行方式
    print("\n4. 关闭持久化的执行方式（无断点续跑能力，性能更好）:")
    pipeline_no_persistence = VideoParsingPipeline(enable_persistence=False)
    result = pipeline_no_persistence.run({
        "video_id": "v_test_002",
        "video_path": "/path/to/test/video2.mp4",
        "video_duration": 15000
    })
    print(f"   执行结果: {'成功' if result['success'] else '失败'}")


def main():
    """主函数：运行所有示例"""
    print("🚀 运行三条流水线示例...\n")

    # 1. 运行视频解析流水线（端到端整合版）
    video_data = example_video_parsing()

    # 2. 运行商品解析流水线
    product_data = example_product_parsing()

    # 3. 运行独立的视频整体理解流水线（可选，演示如何单独使用）
    if video_data:
        overall_data = example_video_overall_parsing(video_data)

    # 4. 运行持久化和断点续跑示例
    example_persistence_and_resume()

    print("\n" + "=" * 60)
    print("🎉 所有流水线示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
