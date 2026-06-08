#!/usr/bin/env python3
"""查询视频解析进度"""
import asyncio
import aiohttp

async def main():
    base_url = "http://localhost:8000"
    username = "admin"
    password = "admin123"

    # 登录
    async with aiohttp.ClientSession() as session:
        login_url = f"{base_url}/v1/auth/login"
        login_data = {"username": username, "password": password}
        async with session.post(login_url, json=login_data) as resp:
            result = await resp.json()
            token = result["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

        # 查询几个较早上传的视频
        video_ids = [19,21,22,24,26,27,28,29,30]
        print("📋 解析进度查询结果：")
        print("-" * 60)

        for video_id in video_ids:
            url = f"{base_url}/v1/admin/video-library/{video_id}/parsing-progress"
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("code") == "0000000":
                        data = result["data"]
                        status = data.get("status")
                        progress = data.get("progress", 0)
                        error = data.get("error_message", "")

                        status_text = {0: "待处理", 1: "处理中", 2: "已完成", 3: "失败"}.get(status, "未知")
                        if status == 2:
                            print(f"✅ 视频ID {video_id}: {status_text} - 进度 {progress}%")
                        elif status == 3:
                            print(f"❌ 视频ID {video_id}: {status_text} - {error}")
                        else:
                            print(f"⏳ 视频ID {video_id}: {status_text} - 进度 {progress}%")
                    else:
                        print(f"⚠️  视频ID {video_id}: 查询失败 - {result.get('message')}")
                else:
                    print(f"❌ 视频ID {video_id}: HTTP错误 {resp.status}")

if __name__ == "__main__":
    asyncio.run(main())
