"""Agent轨迹数据传输对象

定义Agent轨迹相关的请求和响应模型，用于接口参数校验和响应格式规范。
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AgentTraceBase(BaseModel):
    """Agent轨迹基础模型"""
    id: int = Field(description="轨迹ID")
    session_id: str = Field(description="会话ID")
    user_id: Optional[int] = Field(None, description="用户ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    user_input: str = Field(description="用户原始输入")
    model: str = Field(description="使用的模型名称")
    temperature: float = Field(description="模型温度参数")
    max_tokens: int = Field(description="最大生成长度")
    iterations: int = Field(description="推理迭代次数")
    final_answer: Optional[str] = Field(None, description="最终回答内容")
    cost_time: float = Field(description="执行耗时(秒)")
    success: bool = Field(description="是否执行成功")
    error_msg: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(description="创建时间")

    model_config = {
        "from_attributes": True
    }


class AgentTraceDetail(AgentTraceBase):
    """Agent轨迹详情模型（包含完整信息）"""
    system_prompt: str = Field(description="系统提示词")
    top_p: float = Field(description="核采样参数")
    messages_history: List[Dict[str, Any]] = Field(description="完整的消息历史")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="所有工具调用信息")
    tool_results: Optional[List[str]] = Field(None, description="所有工具返回结果")
    metadata: Optional[Dict[str, Any]] = Field(None, description="扩展元数据")


class AgentTraceListResponse(BaseModel):
    """轨迹列表响应"""
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    list: List[AgentTraceBase] = Field(description="轨迹列表")


class TraceQueryRequest(BaseModel):
    """轨迹查询请求参数"""
    session_id: Optional[str] = Field(None, description="按会话ID筛选")
    user_id: Optional[int] = Field(None, description="按用户ID筛选")
    project_id: Optional[int] = Field(None, description="按项目ID筛选")
    model: Optional[str] = Field(None, description="按模型名称筛选")
    success: Optional[bool] = Field(None, description="按执行结果筛选")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    keyword: Optional[str] = Field(None, description="关键词搜索（用户输入/回答）")
    page: int = Field(1, ge=1, description="页码，从1开始")
    page_size: int = Field(20, ge=1, le=100, description="每页数量，最大100")


class TraceStatResponse(BaseModel):
    """轨迹统计响应"""
    total_count: int = Field(description="总调用次数")
    success_count: int = Field(description="成功次数")
    failed_count: int = Field(description="失败次数")
    success_rate: float = Field(description="成功率")
    avg_cost_time: float = Field(description="平均耗时(秒)")
    total_tool_calls: int = Field(description="总工具调用次数")
    period: str = Field(description="统计时间段")
