"""资产接口测试用例"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from PIL import Image

pytestmark = pytest.mark.skip(reason="集成测试：需要真实数据库和 client fixture")


class TestAssetAPI:
    """资产接口测试类"""

    @pytest.fixture(scope="class")
    def test_image_file(self):
        """创建测试图片文件"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            # 创建一个简单的测试图片
            img = Image.new('RGB', (100, 100), color='red')
            img.save(tmp, format='JPEG')
            tmp_path = tmp.name

        yield tmp_path

        # 测试完成后删除临时文件
        os.unlink(tmp_path)

    def test_upload_asset_success(self, client: TestClient, test_image_file: str):
        """测试上传资产成功"""
        with open(test_image_file, "rb") as f:
            files = {"file": ("test_image.jpg", f, "image/jpeg")}
            data = {
                "type": 1,  # 图片类型
                "title": "测试图片资产",
                "source_type": 0
            }
            response = client.post("/generate/v1/assets/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert result["message"] == "上传成功"
        assert "id" in result["data"]
        assert result["data"]["type"] == 1
        assert result["data"]["type_name"] == "图片"
        assert result["data"]["title"] == data["title"]
        assert result["data"]["source_type"] == data["source_type"]
        assert result["data"]["format"] == "jpg"
        assert "url" in result["data"]
        assert "file_size" in result["data"]
        assert "created_at" in result["data"]
        # 保存资产ID供后续测试使用
        pytest.test_asset_id = result["data"]["id"]

    def test_upload_asset_invalid_type(self, client: TestClient, test_image_file: str):
        """测试上传资产类型错误"""
        with open(test_image_file, "rb") as f:
            files = {"file": ("test_image.jpg", f, "image/jpeg")}
            data = {
                "type": 99,  # 无效类型
                "title": "测试图片资产"
            }
            response = client.post("/generate/v1/assets/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "无效的资产类型" in result["message"]

    def test_upload_asset_missing_file(self, client: TestClient):
        """测试上传资产缺少文件"""
        data = {
            "type": 1,
            "title": "测试图片资产"
        }
        response = client.post("/generate/v1/assets/upload", data=data)
        assert response.status_code == 422  # 参数校验失败

    def test_list_assets_default(self, client: TestClient):
        """测试获取资产列表默认参数"""
        response = client.get("/generate/v1/assets")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert "list" in result["data"]
        assert "pagination" in result["data"]
        assert result["data"]["pagination"]["page"] == 1
        assert result["data"]["pagination"]["page_size"] == 20
        assert len(result["data"]["list"]) > 0
        assert "ai_features" in result["data"]["list"][0]
        assert isinstance(result["data"]["list"][0]["ai_features"], dict)

    def test_list_assets_filter_type(self, client: TestClient):
        """测试按类型筛选资产列表"""
        response = client.get("/generate/v1/assets?type=1")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        for item in result["data"]["list"]:
            assert item["type"] == 1
            assert item["type_name"] == "图片"

    def test_list_assets_filter_source_type(self, client: TestClient):
        """测试按来源筛选资产列表"""
        response = client.get("/generate/v1/assets?source_type=0")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        for item in result["data"]["list"]:
            assert item["source_type"] == 0

    def test_list_assets_filter_keyword(self, client: TestClient):
        """测试按关键词搜索资产列表"""
        response = client.get("/generate/v1/assets?keyword=测试图片")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert len(result["data"]["list"]) > 0
        for item in result["data"]["list"]:
            assert "测试图片" in item["title"]

    def test_list_assets_filter_format(self, client: TestClient):
        """测试按格式筛选资产列表"""
        response = client.get("/generate/v1/assets?format=jpg")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        if len(result["data"]["list"]) > 0:
            for item in result["data"]["list"]:
                assert item["format"].lower() == "jpg"

    def test_get_asset_detail_success(self, client: TestClient):
        """测试获取资产详情成功"""
        asset_id = pytest.test_asset_id
        response = client.get(f"/generate/v1/assets/{asset_id}")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert result["data"]["id"] == asset_id
        assert "user_id" in result["data"]
        assert "ai_features" in result["data"]
        assert isinstance(result["data"]["ai_features"], dict)

    def test_get_asset_detail_not_found(self, client: TestClient):
        """测试获取不存在的资产详情"""
        response = client.get("/generate/v1/assets/999999")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "资产不存在" in result["message"]

    def test_update_asset_success(self, client: TestClient):
        """测试更新资产成功"""
        asset_id = pytest.test_asset_id
        update_data = {
            "title": "更新后的测试图片资产",
            "ai_features": {
                "scene": "测试场景",
                "mood": "明亮",
                "objects": ["测试", "图片"]
            }
        }
        response = client.put(f"/generate/v1/assets/{asset_id}", json=update_data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert result["message"] == "更新成功"
        assert result["data"]["id"] == asset_id
        assert result["data"]["title"] == update_data["title"]
        assert "updated_at" in result["data"]

        # 验证更新是否生效
        detail_response = client.get(f"/generate/v1/assets/{asset_id}")
        detail_result = detail_response.json()
        assert detail_result["data"]["title"] == update_data["title"]
        assert detail_result["data"]["ai_features"] == update_data["ai_features"]

    def test_update_asset_partial(self, client: TestClient):
        """测试部分更新资产字段"""
        asset_id = pytest.test_asset_id
        update_data = {
            "ai_features": {
                "scene": "更新后的场景",
                "mood": "温馨",
                "objects": ["新物体1", "新物体2"]
            }
        }
        response = client.put(f"/generate/v1/assets/{asset_id}", json=update_data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0

        # 验证只有ai_features更新了，标题保持不变
        detail_response = client.get(f"/generate/v1/assets/{asset_id}")
        detail_result = detail_response.json()
        assert detail_result["data"]["ai_features"] == update_data["ai_features"]
        assert detail_result["data"]["title"] == "更新后的测试图片资产"

    def test_update_asset_not_found(self, client: TestClient):
        """测试更新不存在的资产"""
        update_data = {
            "title": "更新不存在的资产"
        }
        response = client.put("/generate/v1/assets/999999", json=update_data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "资产不存在" in result["message"]

    def test_delete_asset_success(self, client: TestClient, test_image_file: str):
        """测试删除资产成功"""
        # 先上传一个新资产用于删除测试
        with open(test_image_file, "rb") as f:
            files = {"file": ("test_delete.jpg", f, "image/jpeg")}
            data = {
                "type": 1,
                "title": "待删除的测试图片"
            }
            create_response = client.post("/generate/v1/assets/upload", files=files, data=data)

        asset_id = create_response.json()["data"]["id"]

        # 删除资产
        delete_response = client.delete(f"/generate/v1/assets/{asset_id}")
        assert delete_response.status_code == 200
        delete_result = delete_response.json()
        assert delete_result["code"] == 0
        assert delete_result["message"] == "删除成功"

        # 验证资产已被删除
        detail_response = client.get(f"/generate/v1/assets/{asset_id}")
        detail_result = detail_response.json()
        assert detail_result["code"] != 0
        assert "资产不存在" in detail_result["message"]

    def test_delete_asset_not_found(self, client: TestClient):
        """测试删除不存在的资产"""
        response = client.delete("/generate/v1/assets/999999")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "资产不存在" in result["message"]
