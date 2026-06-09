#!/usr/bin/env python3
"""处理上传结果，生成剩余需要上传的列表"""
import re
from pathlib import Path

def parse_upload_output(output_file):
    """解析上传输出文件"""
    success = set()
    failed = set()
    processed = set()

    with open(output_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 匹配成功上传的视频
    success_matches = re.findall(r"开始处理视频: (E:/hot_video/.*?\.mp4).*?✅ 视频上传成功", content, re.DOTALL)
    for path in success_matches:
        success.add(path)
        processed.add(path)

    # 匹配失败的视频
    failed_matches = re.findall(r"开始处理视频: (E:/hot_video/.*?\.mp4).*?❌ 处理视频失败", content, re.DOTALL)
    for path in failed_matches:
        failed.add(path)
        processed.add(path)

    return success, failed, processed

def main():
    # 读取完整的视频列表
    all_videos = set()
    with open("hot_video_list.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_videos.add(line)

    # 解析上传结果
    output_file = "C:/Users/30118/AppData/Local/Temp/claude/E--project-py-byte-VidMuse/73d8d0a1-4476-446c-ba27-cc00dd2217e1/tasks/befloq3jb.output"
    success, failed, processed = parse_upload_output(output_file)

    # 剩余需要上传的视频
    remaining = all_videos - processed

    print("上传进度统计：")
    print(f"总视频数：{len(all_videos)}")
    print(f"已处理：{len(processed)}")
    print(f"成功上传：{len(success)}")
    print(f"上传失败：{len(failed)}")
    print(f"剩余未处理：{len(remaining)}")

    # 生成剩余列表
    if remaining:
        with open("remaining_videos.txt", "w", encoding="utf-8") as f:
            for path in sorted(remaining):
                f.write(path + "\n")
        print("\n剩余视频列表已保存到: remaining_videos.txt")

    # 生成失败列表
    if failed:
        with open("failed_videos.txt", "w", encoding="utf-8") as f:
            for path in sorted(failed):
                f.write(path + "\n")
        print("失败视频列表已保存到: failed_videos.txt")

    return len(remaining)

if __name__ == "__main__":
    main()
