"""链路追踪管理数据传输对象

定义链路追踪相关的请求和响应模型，用于接口参数校验和响应格式规范。
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TraceBase(BaseModel):
    """Trace基础模型（列表展示用）"""
    id: int = Field(description="Trace ID")
    trace_id: str = Field(description="链路唯一标识")
    method: str = Field(description="HTTP方法")
    path: str = Field(description="请求路径")
    status_code: int = Field(description="响应状态码")
    duration_ms: float = Field(description="总耗时(毫秒)")
    client_ip: Optional[str] = Field(None, description="客户端IP")
    user_id: Optional[int] = Field(None, description="用户ID")
    created_at: datetime = Field(description="创建时间")

    model_config = {
        "from_attributes": True
    }


class TraceDetail(TraceBase):
    """Trace详情模型（包含完整信息）"""
    user_agent: Optional[str] = Field(None, description="用户代理")
    request_headers: Optional[Dict[str, Any]] = Field(None, description="请求头")
    response_headers: Optional[Dict[str, Any]] = Field(None, description="响应头")
    span_count: int = Field(description="关联的Span数量")
    total_span_duration: float = Field(description="所有Span总耗时(毫秒)")


class SpanBase(BaseModel):
    """Span基础模型"""
    id: int = Field(description="Span ID")
    trace_id: str = Field(description="所属链路ID")
    span_id: str = Field(description="Span唯一标识")
    parent_span_id: Optional[str] = Field(None, description="父Span ID")
    name: str = Field(description="函数名/操作名")
    class_name: Optional[str] = Field(None, description="类名")
    module_name: str = Field(description="模块名")
    start_time: float = Field(description="开始时间戳(秒)")
    end_time: float = Field(description="结束时间戳(秒)")
    duration_ms: float = Field(description="耗时(毫秒)")
    has_exception: bool = Field(description="是否有异常")
    created_at: datetime = Field(description="创建时间")

    model_config = {
        "from_attributes": True
    }


class SpanDetail(SpanBase):
    """Span详情模型（包含完整信息）"""
    args: Optional[List[Any]] = Field(None, description="位置参数")
    kwargs: Optional[Dict[str, Any]] = Field(None, description="关键字参数")
    return_value: Optional[Any] = Field(None, description="返回值")
    exception: Optional[str] = Field(None, description="异常信息")
    stack_trace: Optional[str] = Field(None, description="调用堆栈")
    meta_data: Optional[Dict[str, Any]] = Field(None, description="扩展元数据")
    child_spans: Optional[List["SpanDetail"]] = Field(None, description="子Span列表")


class TraceListResponse(BaseModel):
    """Trace列表响应"""
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    list: List[TraceBase] = Field(description="Trace列表")


class SpanListResponse(BaseModel):
    """Span列表响应"""
    trace_id: str = Field(description="链路ID")
    total: int = Field(description="总Span数量")
    list: List[SpanBase] = Field(description="Span列表")
    tree: Optional[List[SpanDetail]] = Field(None, description="Span树形结构")


class TraceQueryRequest(BaseModel):
    """Trace查询请求参数"""
    trace_id: Optional[str] = Field(None, description="按链路ID筛选")
    method: Optional[str] = Field(None, description="按HTTP方法筛选")
    path: Optional[str] = Field(None, description="按请求路径模糊匹配")
    status_code: Optional[int] = Field(None, description="按响应状态码筛选")
    min_duration: Optional[float] = Field(None, description="最小耗时(毫秒)")
    max_duration: Optional[float] = Field(None, description="最大耗时(毫秒)")
    client_ip: Optional[str] = Field(None, description="按客户端IP筛选")
    user_id: Optional[int] = Field(None, description="按用户ID筛选")
    has_exception: Optional[bool] = Field(None, description="是否包含异常")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(1, ge=1, description="页码，从1开始")
    page_size: int = Field(20, ge=1, le=200, description="每页数量，最大200")


class TraceStatResponse(BaseModel):
    """Trace统计响应"""
    total_count: int = Field(description="总请求次数")
    success_count: int = Field(description="成功次数（状态码2xx/3xx）")
    error_count: int = Field(description="错误次数（状态码4xx/5xx）")
    success_rate: float = Field(description="成功率")
    avg_duration: float = Field(description="平均耗时(毫秒)")
    p50_duration: float = Field(description="P50耗时(毫秒)")
    p95_duration: float = Field(description="P95耗时(毫秒)")
    p99_duration: float = Field(description="P99耗时(毫秒)")
    total_span_count: int = Field(description="总Span数量")
    avg_span_per_trace: float = Field(description="平均每个Trace的Span数量")
    period: str = Field(description="统计时间段")


# 修复前向引用
SpanDetail.model_rebuild()
