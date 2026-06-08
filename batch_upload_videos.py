#!/usr/bin/env python3
"""
批量上传并解析视频脚本
支持两种模式：
1. 通过URL批量上传公开视频
2. 批量上传本地视频文件
"""
import os
import sys
import time
import json
import tempfile
import asyncio
import aiohttp
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

# 修复Windows控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

@dataclass
class VideoItem:
    """视频项"""
    source: str  # 文件路径或URL
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class VideoUploader:
    """视频上传器"""

    def __init__(self, base_url: str = "http://localhost:8000", username: str = "admin", password: str = "admin123"):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def login(self) -> None:
        """登录获取token"""
        login_url = f"{self.base_url}/v1/auth/login"
        data = {
            "username": self.username,
            "password": self.password
        }

        async with self.session.post(login_url, json=data) as response:
            if response.status != 200:
                raise Exception(f"登录失败: {response.status} - {await response.text()}")

            result = await response.json()
            if result.get("code") != "0000000":
                raise Exception(f"登录失败: {result.get('message')}")

            self.access_token = result["data"]["access_token"]
            self.refresh_token = result["data"]["refresh_token"]
            print("✅ 登录成功")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        if not self.access_token:
            raise Exception("未登录")

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }


    async def upload_video_by_file(self, video: VideoItem, trigger_parse: bool = True) -> Dict:
        """上传本地视频文件"""
        url = f"{self.base_url}/v1/admin/video-library/upload"

        if not os.path.exists(video.source):
            raise Exception(f"文件不存在: {video.source}")

        form = aiohttp.FormData()
        form.add_field("file", open(video.source, "rb"), filename=os.path.basename(video.source))

        if video.title:
            form.add_field("title", video.title)
        if video.description:
            form.add_field("description", video.description)
        if video.category:
            form.add_field("category", video.category)
        if video.tags:
            for tag in video.tags:
                form.add_field("tags", tag)

        form.add_field("trigger_ai_parse", str(trigger_parse).lower())

        async with self.session.post(url, data=form, headers=self._get_headers()) as response:
            if response.status != 200:
                raise Exception(f"上传视频失败: {response.status} - {await response.text()}")

            result = await response.json()
            if result.get("code") != "0000000":
                raise Exception(f"上传视频失败: {result.get('message')}")

            return result["data"]

    async def trigger_parse(self, video_id: int, force: bool = False) -> bool:
        """触发视频解析"""
        url = f"{self.base_url}/v1/admin/video-library/{video_id}/parse?force={str(force).lower()}"

        async with self.session.post(url, headers=self._get_headers()) as response:
            if response.status != 200:
                print(f"❌ 触发解析失败 (ID: {video_id}): {response.status} - {await response.text()}")
                return False

            result = await response.json()
            if result.get("code") != "0000000":
                print(f"❌ 触发解析失败 (ID: {video_id}): {result.get('message')}")
                return False

            print(f"✅ 解析任务已触发 (ID: {video_id})")
            return True

    async def get_parsing_progress(self, video_id: int) -> Optional[Dict]:
        """查询解析进度"""
        url = f"{self.base_url}/v1/admin/video-library/{video_id}/parsing-progress"

        async with self.session.get(url, headers=self._get_headers()) as response:
            if response.status != 200:
                return None

            result = await response.json()
            if result.get("code") != "0000000":
                return None

            return result["data"]

    async def wait_for_parse_complete(self, video_id: int, timeout: int = 300, poll_interval: int = 5) -> Optional[Dict]:
        """等待解析完成"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            progress = await self.get_parsing_progress(video_id)
            if not progress:
                print(f"⚠️  无法获取进度 (ID: {video_id})")
                return None

            status = progress.get("status")
            progress_pct = progress.get("progress", 0)

            if status == 2:  # 已完成
                print(f"✅ 解析完成 (ID: {video_id}) - 进度: {progress_pct}%")
                return progress
            elif status == 3:  # 失败
                print(f"❌ 解析失败 (ID: {video_id}) - 错误: {progress.get('error_message')}")
                return progress

            print(f"⏳ 解析中 (ID: {video_id}) - 进度: {progress_pct}% - 状态: {status}")
            await asyncio.sleep(poll_interval)

        print(f"⏰ 解析超时 (ID: {video_id})")
        return None

    async def download_video(self, url: str, temp_dir: str) -> str:
        """下载视频到临时文件"""
        filename = os.path.basename(url.split("?")[0])
        if not filename or "." not in filename:
            filename = f"temp_video_{int(time.time())}.mp4"

        temp_path = os.path.join(temp_dir, filename)

        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"下载视频失败: {response.status}")

            with open(temp_path, "wb") as f:
                while True:
                    chunk = await response.content.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    f.write(chunk)

        return temp_path

    async def process_video(self, video: VideoItem, use_url: bool = False, wait_complete: bool = True, trigger_parse: bool = True) -> Dict:
        """处理单个视频"""
        temp_file = None
        try:
            print(f"\n📹 开始处理视频: {video.source}")

            # 上传视频
            if use_url:
                # 先下载到临时文件
                print(f"⏳ 正在下载视频: {video.source}")
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_file = await self.download_video(video.source, temp_dir)
                    print(f"✅ 视频下载完成: {temp_file}")

                    # 创建临时VideoItem
                    temp_video = VideoItem(
                        source=temp_file,
                        title=video.title or os.path.basename(video.source.split("?")[0]),
                        description=video.description,
                        category=video.category,
                        tags=video.tags
                    )

                    # 使用文件上传接口
                    video_data = await self.upload_video_by_file(temp_video, trigger_parse=trigger_parse)
                    print(f"✅ 视频上传成功 (ID: {video_data['id']}, URL: {video_data['url']})")
            else:
                video_data = await self.upload_video_by_file(video, trigger_parse=trigger_parse)
                print(f"✅ 视频上传成功 (ID: {video_data['id']}, URL: {video_data['url']})")

            # 等待解析完成
            result = {
                "success": True,
                "source": video.source,
                "video_data": video_data,
                "parse_result": None
            }

            if wait_complete and trigger_parse:
                parse_result = await self.wait_for_parse_complete(video_data["id"])
                result["parse_result"] = parse_result

            return result

        except Exception as e:
            print(f"❌ 处理视频失败 {video.source}: {str(e)}")
            return {
                "success": False,
                "source": video.source,
                "error": str(e)
            }
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass

    async def process_videos(self, videos: List[VideoItem], use_url: bool = False, wait_complete: bool = True, trigger_parse: bool = True, max_concurrent: int = 3) -> List[Dict]:
        """批量处理视频"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(video: VideoItem) -> Dict:
            async with semaphore:
                return await self.process_video(video, use_url, wait_complete, trigger_parse)

        tasks = [process_with_semaphore(video) for video in videos]
        results = await asyncio.gather(*tasks)

        return results

def load_videos_from_file(file_path: str) -> List[VideoItem]:
    """从文件加载视频列表
    支持格式：
    1. 纯文本：每行一个URL或文件路径
    2. JSON格式：[{"source": "url/path", "title": "...", ...}, ...]
    """
    if not os.path.exists(file_path):
        raise Exception(f"文件不存在: {file_path}")

    # 尝试JSON格式
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [VideoItem(**item) for item in data]
    except json.JSONDecodeError:
        pass

    # 纯文本格式
    videos = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                videos.append(VideoItem(source=line))

    return videos

async def main():
    parser = argparse.ArgumentParser(description="批量上传并解析视频")
    parser.add_argument("--url", action="store_true", help="通过URL上传（默认是本地文件）")
    parser.add_argument("--no-parse", action="store_true", help="不触发AI解析")
    parser.add_argument("--no-wait", action="store_true", help="不等待解析完成")
    parser.add_argument("--server", default="http://localhost:8000", help="服务器地址")
    parser.add_argument("--username", default="admin", help="用户名")
    parser.add_argument("--password", default="admin123", help="密码")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数")
    parser.add_argument("--output", help="结果输出文件路径")
    parser.add_argument("sources", nargs="+", help="视频源（文件路径、URL或列表文件）")

    args = parser.parse_args()

    # 加载视频列表
    videos = []
    for source in args.sources:
        if os.path.isfile(source) and (source.endswith(".txt") or source.endswith(".json")):
            # 是列表文件
            videos.extend(load_videos_from_file(source))
        else:
            # 是单个视频源
            videos.append(VideoItem(source=source))

    if not videos:
        print("❌ 没有可处理的视频")
        return

    print(f"📋 共找到 {len(videos)} 个视频待处理")

    # 处理视频
    async with VideoUploader(
        base_url=args.server,
        username=args.username,
        password=args.password
    ) as uploader:
        results = await uploader.process_videos(
            videos=videos,
            use_url=args.url,
            wait_complete=not args.no_wait,
            trigger_parse=not args.no_parse,
            max_concurrent=args.concurrency
        )

    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count

    print(f"\n📊 处理完成: 成功 {success_count} 个, 失败 {failed_count} 个")

    # 输出结果
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"📝 结果已保存到: {args.output}")
    else:
        # 打印简要结果
        for result in results:
            if result["success"]:
                video_id = result["video_data"]["id"]
                print(f"✅ {result['source']} (ID: {video_id})")
            else:
                print(f"❌ {result['source']}: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())
