# 灵感模板TextToSQL工具使用说明

## 概述
灵感模板TextToSQL工具允许用户通过自然语言查询灵感模板模块的相关数据，系统会自动生成并执行安全的SQL查询，返回格式化的结果。

## 功能特性
- ✅ 支持自然语言转SQL查询
- ✅ 支持4张灵感模板相关表的查询
- ✅ 多层安全验证，防止SQL注入和非法操作
- ✅ 自动过滤已删除数据
- ✅ 支持单表查询和多表关联查询
- ✅ 结果自动格式化返回

## 支持的表
1. **factors** - 创作因子表
2. **strategies** - 创作策略表  
3. **inspiration_templates** - 灵感模板表
4. **template_factor_relations** - 模板-因子关联表

## 工具调用方式
### 基本参数
```python
{
    "query": "自然语言查询语句",
    "limit": 10  # 可选，默认10条
}
```

### 调用示例
```python
from backend.v1.app.agent.tools.text_to_sql_inspiration_tool import TextToSQLInspirationTool

tool = TextToSQLInspirationTool()
result = tool.execute({
    "query": "查询流行度大于0.8的创作因子",
    "limit": 20
})
```

### 返回结果格式
```json
{
    "success": true,
    "query": "查询流行度大于0.8的创作因子",
    "generated_sql": "SELECT * FROM factors WHERE is_deleted = 0 AND popularity > 0.8 LIMIT 20",
    "data": [
        {
            "id": 1,
            "factor_id": "factor_001",
            "name": "痛点开场",
            "popularity": 0.85,
            ...
        }
    ]
}
```

## 常见查询示例
1. **查询高流行度因子**：`"查询流行度大于0.8的创作因子"`
2. **查询高成功率策略**：`"查找成功率最高的前5个创作策略"`
3. **查询最新模板**：`"查询最近创建的10个灵感模板"`
4. **统计因子类型**：`"统计每个类型的因子数量"`
5. **按场景查询策略**：`"查找适用场景包含'美妆'的策略"`
6. **关联查询模板因子**：`"查询包含'痛点呈现'因子的灵感模板"`

## 安全限制
- 只能执行SELECT查询，禁止任何数据修改操作
- 只能查询4张灵感模板相关的表
- 自动过滤已删除数据（is_deleted = 0）
- 查询结果数量最多限制为100条
- 禁止危险关键字：DROP、ALTER、DELETE、INSERT、UPDATE等

## 注意事项
- 复杂查询可能需要更精确的描述
- 如果生成的SQL不符合预期，可以尝试调整查询语句的表达方式
- 关联查询时建议明确说明表之间的关系
- JSON字段查询需要说明是数组还是对象类型
