"""任务调度相关的数据传输对象"""
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from enum import Enum


class TaskTypeEnum(str, Enum):
    """任务类型枚举"""
    VIDEO_PRODUCTION = "video_production"
    VIDEO_ANALYSIS = "video_analysis"
    SCHEDULED_CLUSTERING = "scheduled_clustering"
    DEFAULT = "default"


class TaskStatusEnum(str, Enum):
    """任务状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskSubmitRequest(BaseModel):
    """任务提交请求"""
    task_type: TaskTypeEnum = Field(..., description="任务类型")
    payload: Dict[str, Any] = Field(..., description="任务业务参数")
    priority: int = Field(default=3, ge=1, le=5, description="优先级（1-5，越小优先级越高）")
    user_id: Optional[int] = Field(default=None, description="关联用户ID")


class TaskSubmitResponse(BaseModel):
    """任务提交响应"""
    task_id: str = Field(..., description="任务ID")
    trace_id: str = Field(..., description="链路追踪ID")
    status: TaskStatusEnum = Field(..., description="任务状态")
    message: str = Field(..., description="提示信息")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    trace_id: str = Field(..., description="链路追踪ID")
    task_type: TaskTypeEnum = Field(..., description="任务类型")
    status: TaskStatusEnum = Field(..., description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    started_at: Optional[str] = Field(default=None, description="开始执行时间")
    finished_at: Optional[str] = Field(default=None, description="结束时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    result: Optional[Dict[str, Any]] = Field(default=None, description="执行结果")
    user_id: Optional[int] = Field(default=None, description="关联用户ID")


class TaskCancelResponse(BaseModel):
    """任务取消响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
