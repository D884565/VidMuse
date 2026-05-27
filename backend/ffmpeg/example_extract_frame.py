"""
根据时间戳提取视频帧 - 使用示例
"""
import os
from backend.ffmpeg.pyutils import FFmpegVideoProcessor

def example_file_mode():
    """示例：从本地视频文件提取帧"""
    # 替换为你的视频路径
    video_path = "E:\\video\\v1.mp4"

    if not os.path.exists(video_path):
        print(f"视频文件不存在: {video_path}")
        return

    # 初始化处理器
    processor = FFmpegVideoProcessor(video_path)

    # 示例1: 提取第5.2秒的帧为numpy数组
    print("示例1: 提取第5.2秒的帧为numpy数组")
    frame = processor.extract_frame_by_timestamp(5.2)
    print(f"帧数据 shape: {frame.shape}, dtype: {frame.dtype}")
    print(f"帧数据范围: min={frame.min()}, max={frame.max()}")

    # 示例2: 提取第10秒的帧保存为PNG文件
    print("\n示例2: 提取第10秒的帧保存为PNG文件")
    processor.extract_frame_by_timestamp(10.0, output_path="E:\\video\\res")
    print("已保存为 E:\\video\\res\\frame_10s.png")

    # 示例3: 提取第15.5秒的帧保存为高质量JPG
    print("\n示例3: 提取第15.5秒的帧保存为高质量JPG")
    processor.extract_frame_by_timestamp(15.5, output_path="E:\\video\\res", quality=1)
    print("已保存为 E:\\video\\res\\frame_15s.jpg")

    # 示例5: 直接输出到目录（自动生成文件名）
    print("\n示例5: 直接输出到目录（自动生成文件名）")
    output_dir = "E:\\video\\res"
    processor.extract_frame_by_timestamp(7.5, output_path=output_dir, format="jpg")
    print(f"已自动保存到 {output_dir} 目录下")

    # 示例4: 使用HH:MM:SS格式时间戳
    print("\n示例4: 使用HH:MM:SS格式时间戳")
    frame = processor.extract_frame_by_timestamp("00:00:20.5")
    print(f"第20.5秒帧 shape: {frame.shape}")

def example_memory_mode():
    """示例：从内存字节流提取帧"""
    # 替换为你的视频路径
    video_path = "input.mp4"

    if not os.path.exists(video_path):
        print(f"视频文件不存在: {video_path}")
        return

    # 读取视频到内存
    print("\n读取视频到内存...")
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    print(f"视频大小: {len(video_bytes) / 1024 / 1024:.2f} MB")

    # 示例1: 从内存提取第3秒的帧为numpy数组
    print("\n示例1: 从内存提取第3秒的帧为numpy数组")
    frame = FFmpegVideoProcessor.extract_frame_by_timestamp_in_memory(video_bytes, 3.0)
    print(f"帧数据 shape: {frame.shape}")

    # 示例2: 从内存提取帧并保存到文件
    print("\n示例2: 从内存提取帧并保存到文件")
    FFmpegVideoProcessor.extract_frame_by_timestamp_in_memory(
        video_bytes, "00:00:07", output_path="memory_frame_7s.png"
    )
    print("已保存为 memory_frame_7s.png")

if __name__ == "__main__":
    print("=" * 60)
    print("FFmpeg 帧提取功能使用示例")
    print("=" * 60)

    print("\n📁 文件模式示例:")
    example_file_mode()

    print("\n" + "=" * 60)

    print("\n💾 内存模式示例:")
    # example_memory_mode()

    print("\n" + "=" * 60)
    print("✅ 所有示例执行完成！")
