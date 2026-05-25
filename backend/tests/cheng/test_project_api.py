"""项目接口测试用例"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestProjectAPI:
    """项目接口测试类"""

    def test_create_project_success(self, client: TestClient):
        """测试创建项目成功"""
        data = {
            "title": "测试项目标题",
            "description": "这是一个测试项目描述",
            "product_url": "https://example.com/product/123",
            "product_id": 20001
        }
        response = client.post("/generate/v1/projects", json=data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert result["message"] == "项目创建成功"
        assert "id" in result["data"]
        assert result["data"]["title"] == data["title"]
        assert result["data"]["description"] == data["description"]
        assert result["data"]["product_url"] == data["product_url"]
        assert result["data"]["product_id"] == data["product_id"]
        assert result["data"]["status"] == 0
        assert result["data"]["status_name"] == "待生成"
        assert "created_at" in result["data"]
        assert "updated_at" in result["data"]
        # 保存项目ID供后续测试使用
        pytest.test_project_id = result["data"]["id"]

    def test_create_project_missing_title(self, client: TestClient):
        """测试创建项目缺少标题"""
        data = {
            "description": "这是一个测试项目描述",
            "product_url": "https://example.com/product/123"
        }
        response = client.post("/generate/v1/projects", json=data)
        assert response.status_code == 422  # 参数校验失败

    def test_create_project_title_too_long(self, client: TestClient):
        """测试创建项目标题过长"""
        data = {
            "title": "测" * 201,
            "description": "这是一个测试项目描述"
        }
        response = client.post("/generate/v1/projects", json=data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0  # 业务错误
        assert "标题不能超过200字符" in result["message"]

    def test_create_project_product_url_too_long(self, client: TestClient):
        """测试创建项目商品链接过长"""
        data = {
            "title": "测试项目",
            "product_url": "https://example.com/" + "a" * 1000
        }
        response = client.post("/generate/v1/projects", json=data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "商品链接不能超过1000字符" in result["message"]

    def test_list_projects_default(self, client: TestClient):
        """测试获取项目列表默认参数"""
        response = client.get("/generate/v1/projects")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert "list" in result["data"]
        assert "pagination" in result["data"]
        assert result["data"]["pagination"]["page"] == 1
        assert result["data"]["pagination"]["page_size"] == 20
        assert len(result["data"]["list"]) > 0

    def test_list_projects_filter_status(self, client: TestClient):
        """测试按状态筛选项目列表"""
        response = client.get("/generate/v1/projects?status=0")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        for item in result["data"]["list"]:
            assert item["status"] == 0

    def test_list_projects_filter_keyword(self, client: TestClient):
        """测试按关键词搜索项目列表"""
        response = client.get("/generate/v1/projects?keyword=测试项目")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert len(result["data"]["list"]) > 0
        for item in result["data"]["list"]:
            assert "测试项目" in item["title"]

    def test_list_projects_pagination(self, client: TestClient):
        """测试项目列表分页"""
        response = client.get("/generate/v1/projects?page=1&page_size=1")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert len(result["data"]["list"]) == 1
        assert result["data"]["pagination"]["page"] == 1
        assert result["data"]["pagination"]["page_size"] == 1

    def test_get_project_detail_success(self, client: TestClient):
        """测试获取项目详情成功"""
        project_id = pytest.test_project_id
        response = client.get(f"/generate/v1/projects/{project_id}")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert result["data"]["id"] == project_id
        assert "frames" in result["data"]
        assert isinstance(result["data"]["frames"], list)

    def test_get_project_detail_not_found(self, client: TestClient):
        """测试获取不存在的项目详情"""
        response = client.get("/generate/v1/projects/999999")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "项目不存在" in result["message"]

    def test_update_project_success(self, client: TestClient):
        """测试更新项目成功"""
        project_id = pytest.test_project_id
        update_data = {
            "title": "更新后的测试项目标题",
            "description": "更新后的项目描述"
        }
        response = client.put(f"/generate/v1/projects/{project_id}", json=update_data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0
        assert result["message"] == "项目更新成功"
        assert result["data"]["id"] == project_id
        assert result["data"]["title"] == update_data["title"]
        assert "updated_at" in result["data"]

        # 验证更新是否生效
        detail_response = client.get(f"/generate/v1/projects/{project_id}")
        detail_result = detail_response.json()
        assert detail_result["data"]["title"] == update_data["title"]
        assert detail_result["data"]["description"] == update_data["description"]

    def test_update_project_partial(self, client: TestClient):
        """测试部分更新项目字段"""
        project_id = pytest.test_project_id
        update_data = {
            "product_url": "https://example.com/updated/product/456"
        }
        response = client.put(f"/generate/v1/projects/{project_id}", json=update_data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] == 0

        # 验证只有product_url更新了，标题保持不变
        detail_response = client.get(f"/generate/v1/projects/{project_id}")
        detail_result = detail_response.json()
        assert detail_result["data"]["product_url"] == update_data["product_url"]
        assert detail_result["data"]["title"] == "更新后的测试项目标题"

    def test_update_project_not_found(self, client: TestClient):
        """测试更新不存在的项目"""
        update_data = {
            "title": "更新不存在的项目"
        }
        response = client.put("/generate/v1/projects/999999", json=update_data)
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "项目不存在" in result["message"]

    def test_delete_project_success(self, client: TestClient):
        """测试删除项目成功"""
        # 先创建一个新项目用于删除测试
        create_data = {
            "title": "待删除的测试项目",
            "description": "这个项目会被删除"
        }
        create_response = client.post("/generate/v1/projects", json=create_data)
        project_id = create_response.json()["data"]["id"]

        # 删除项目
        delete_response = client.delete(f"/generate/v1/projects/{project_id}")
        assert delete_response.status_code == 200
        delete_result = delete_response.json()
        assert delete_result["code"] == 0
        assert delete_result["message"] == "项目删除成功"

        # 验证项目已被删除
        detail_response = client.get(f"/generate/v1/projects/{project_id}")
        detail_result = detail_response.json()
        assert detail_result["code"] != 0
        assert "项目不存在" in detail_result["message"]

    def test_delete_project_not_found(self, client: TestClient):
        """测试删除不存在的项目"""
        response = client.delete("/generate/v1/projects/999999")
        assert response.status_code == 200
        result = response.json()
        assert result["code"] != 0
        assert "项目不存在" in result["message"]
