"""
TOS 客户端测试脚本
注意：运行前请确保已在 .env 文件中配置正确的 TOS 参数
"""
import os
from dotenv import load_dotenv
from backend.store import get_tos_client

# 加载环境变量

load_dotenv()
def test_tos_client():
    """测试TOS客户端基本功能"""
    try:
        # 初始化客户端
        client = get_tos_client()
        print("TOS客户端初始化成功")

        # 测试文件路径
        test_file_path = "/obj"
        test_object_name = "test/test_tos_upload.txt"

        # 创建测试文件
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write("一遍过")
        print(f"测试文件已创建: {test_file_path}")

        # 测试上传文件
        url = client.upload_file(test_file_path, test_object_name, "text/plain")
        print(f"文件上传成功，访问URL: {url}")

        # 测试检查对象是否存在
        exists = client.object_exists(test_object_name)
        print(f"对象存在检查: {'存在' if exists else '不存在'}")

        # 测试获取预签名URL
        presigned_url = client.get_presigned_url(test_object_name)
        print(f"预签名URL: {presigned_url}")

        # 测试下载文件
        download_path = "test_tos_download.txt"
        client.download_file(test_object_name, download_path)
        print(f"文件下载成功，保存到: {download_path}")

        # 验证下载内容
        with open(download_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"下载文件内容: {content}")

        # 测试删除对象
        client.delete_object(test_object_name)
        print("对象删除成功")

        # 验证删除后对象不存在
        exists = client.object_exists(test_object_name)
        print(f"删除后对象存在检查: {'存在' if exists else '不存在'}")

        # 清理本地测试文件
        os.remove(test_file_path)
        os.remove(download_path)
        print("本地测试文件已清理")

        print("\n所有测试通过！")

    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tos_client()
