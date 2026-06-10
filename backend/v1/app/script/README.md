# 剧本模块 - 灵感模板查询功能

## 模块概述

本模块为用户提供灵感模板相关的查询功能，包括模板、策略、因子的列表查询、详情查询、热门推荐和全局搜索等功能。所有接口均为只读接口，不涉及数据修改操作。

## 目录结构

```
script/
├── dao/
│   ├── __init__.py
│   └── inspiration_template_dao.py    # 灵感模板数据访问层
├── service/
│   ├── __init__.py
│   ├── inspiration_template_query_service.py  # 灵感模板查询服务
│   ├── script_generation_service.py
│   └── template_script_service.py
├── controller/
│   ├── __init__.py
│   └── script_controller.py  # API路由（新增灵感模板相关接口）
├── __init__.py
└── README.md
```

## 功能特性

### 1. 灵感模板管理
- 分页查询模板列表（支持多条件筛选）
- 获取模板详情（包含关联的策略和因子信息）
- 获取热门模板推荐

### 2. 创作策略管理
- 分页查询策略列表（支持多条件筛选）
- 获取策略详情（包含关联的模板列表）
- 热门策略推荐

### 3. 创作因子管理
- 分页查询因子列表（支持多条件筛选）
- 获取因子详情（包含使用该因子的模板列表）
- 热门因子推荐

### 4. 综合功能
- 热门推荐（同时返回热门模板、策略、因子）
- 全局搜索（支持在模板、策略、因子中统一搜索关键词）

## API接口列表

### 模板相关接口

| 接口路径 | 方法 | 描述 |
|---------|------|------|
| `/script/v1/inspiration/template/list` | GET | 分页查询灵感模板列表 |
| `/script/v1/inspiration/template/detail` | GET | 获取灵感模板详情 |

### 策略相关接口

| 接口路径 | 方法 | 描述 |
|---------|------|------|
| `/script/v1/inspiration/strategy/list` | GET | 分页查询创作策略列表 |
| `/script/v1/inspiration/strategy/detail` | GET | 获取创作策略详情 |

### 因子相关接口

| 接口路径 | 方法 | 描述 |
|---------|------|------|
| `/script/v1/inspiration/factor/list` | GET | 分页查询创作因子列表 |
| `/script/v1/inspiration/factor/detail` | GET | 获取创作因子详情 |

### 综合接口

| 接口路径 | 方法 | 描述 |
|---------|------|------|
| `/script/v1/inspiration/hot` | GET | 获取热门推荐（模板、策略、因子） |
| `/script/v1/inspiration/search` | GET | 全局搜索灵感模板、策略、因子 |

## 使用示例

### 1. 查询模板列表

```python
import requests

response = requests.get(
    "http://localhost:8000/script/v1/inspiration/template/list",
    params={
        "page": 1,
        "page_size": 10,
        "keyword": "美妆",
        "min_success_rate": 0.8,
        "include_basic_info": True
    }
)

result = response.json()
print(f"总数量: {result['data']['total']}")
print(f"模板列表: {result['data']['list']}")
```

### 2. 获取模板详情

```python
import requests

response = requests.get(
    "http://localhost:8000/script/v1/inspiration/template/detail",
    params={
        "template_id": "TPL202401010001",
        "include_strategy": True,
        "include_factors": True
    }
)

template = response.json()["data"]
print(f"模板名称: {template['name']}")
print(f"关联策略: {template.get('strategy', {}).get('name')}")
print(f"关联因子数量: {len(template.get('factors', []))}")
```

### 3. 全局搜索

```python
import requests

response = requests.get(
    "http://localhost:8000/script/v1/inspiration/search",
    params={
        "keyword": "剧情反转",
        "limit_per_type": 5
    }
)

result = response.json()["data"]
print(f"匹配的模板: {len(result['templates'])}个")
print(f"匹配的策略: {len(result['strategies'])}个")
print(f"匹配的因子: {len(result['factors'])}个")
```

### 4. 获取热门推荐

```python
import requests

response = requests.get(
    "http://localhost:8000/script/v1/inspiration/hot",
    params={
        "template_limit": 10,
        "strategy_limit": 5,
        "factor_limit": 10
    }
)

hot = response.json()["data"]
print(f"热门模板: {[t['name'] for t in hot['hot_templates']]}")
print(f"热门策略: {[s['name'] for s in hot['hot_strategies']]}")
print(f"热门因子: {[f['name'] for f in hot['hot_factors']]}")
```

## 服务层调用示例

如果需要在代码中直接调用服务，可以使用以下方式：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from backend.v1.app.script.service import inspiration_template_query_service

async def get_template_list_example(db: AsyncSession):
    # 查询模板列表
    total, templates = await inspiration_template_query_service.list_templates(
        db=db,
        keyword="美妆",
        min_success_rate=0.8,
        page=1,
        page_size=10
    )
    
    # 获取模板详情
    template_detail = await inspiration_template_query_service.get_template_detail(
        db=db,
        template_id="TPL202401010001"
    )
    
    return templates
```

## 数据模型说明

### 模板(InspirationTemplate)
- `template_id`: 全局唯一模板ID
- `strategy_id`: 关联的策略ID
- `name`: 模板名称
- `description`: 模板描述
- `combination_example`: 完整组合示例
- `version`: 版本号
- `success_rate`: 模板成功率（0-1）
- `usage_count`: 使用次数统计

### 策略(Strategy)
- `strategy_id`: 全局唯一策略ID
- `name`: 策略名称
- `description`: 策略描述
- `applicable_scenarios`: 适用场景列表
- `core_logic`: 核心创作逻辑描述
- `required_factor_types`: 必填因子类型列表
- `optional_factor_types`: 可选因子类型列表
- `combination_rules`: 因子组合规则描述
- `success_rate`: 历史爆款成功率（0-1）
- `tags`: 标签列表
- `usage_count`: 使用次数统计

### 因子(Factor)
- `factor_id`: 全局唯一因子ID
- `factor_type`: 因子类型：content_structure/product_expression/user_operation
- `name`: 因子名称
- `description`: 因子详细描述
- `applicable_scenarios`: 适用场景列表
- `data_schema`: 因子数据结构定义
- `example`: 因子示例数据
- `tags`: 标签列表
- `popularity`: 流行度（0-1）
- `usage_count`: 使用次数统计

## 注意事项

1. 所有接口均为只读接口，不支持数据的增删改操作
2. 分页查询默认页码从1开始，每页数量最大支持100条
3. 成功率和流行度的取值范围均为0-1
4. 所有时间字段均返回ISO格式的字符串
