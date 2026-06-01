"""
全链路追踪系统使用示例

1. 安装依赖
2. 配置中间件
3. 使用装饰器标记需要追踪的函数
4. 查询链路数据
"""

from fastapi import FastAPI
from backend.trace import TraceMiddleware, trace, get_trace_id

# 创建FastAPI应用
app = FastAPI(title="Trace System Demo")

# 添加链路追踪中间件
app.add_middleware(TraceMiddleware)


# 示例1：追踪普通函数
@trace
def add(a: int, b: int) -> int:
    """加法函数"""
    return a + b


# 示例2：追踪异步函数
@trace(name="异步乘法", meta_data={"category": "math"})
async def multiply(a: int, b: int) -> int:
    """乘法函数"""
    import asyncio
    await asyncio.sleep(0.01)
    return a * b


# 示例3：追踪类方法
class Calculator:
    @trace
    def subtract(self, a: int, b: int) -> int:
        """减法方法"""
        return a - b

    @classmethod
    @trace
    def divide(cls, a: int, b: int) -> float:
        """除法类方法"""
        if b == 0:
            raise ValueError("Division by zero")
        return a / b


# 示例4：API接口
@app.get("/calculate")
async def calculate(a: int, b: int):
    """计算接口"""
    sum_result = add(a, b)
    product_result = await multiply(a, b)

    calc = Calculator()
    diff_result = calc.subtract(a, b)
    div_result = Calculator.divide(a, b)

    return {
        "sum": sum_result,
        "product": product_result,
        "difference": diff_result,
        "quotient": div_result,
        "trace_id": get_trace_id()
    }


# 示例5：异常场景
@app.get("/error")
@trace
async def error_demo():
    """异常示例"""
    raise ValueError("This is a test error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


"""
查询链路数据示例SQL：

1. 查询最近1小时的请求：
SELECT * FROM traces
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
ORDER BY created_at DESC;

2. 根据trace_id查询完整调用链：
SELECT * FROM spans
WHERE trace_id = 'your_trace_id'
ORDER BY start_time ASC;

3. 查询慢请求（耗时超过1秒）：
SELECT * FROM traces
WHERE duration_ms > 1000
ORDER BY duration_ms DESC;

4. 查询异常请求：
SELECT * FROM traces
WHERE status_code >= 500
ORDER BY created_at DESC;

5. 查询某个函数的调用统计：
SELECT name, COUNT(*) as count, AVG(duration_ms) as avg_duration
FROM spans
WHERE name = 'add'
GROUP BY name;
"""
