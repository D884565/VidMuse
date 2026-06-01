import contextvars
import time
import traceback
import uuid
from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field


# 上下文变量
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id",
    default=""
)
span_stack_var: contextvars.ContextVar[List["Span"]] = contextvars.ContextVar("span_stack")


@dataclass
class Span:
    name: str
    module_name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    trace_id: str = field(default_factory=lambda: trace_id_var.get())
    parent_span_id: Optional[str] = None
    class_name: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    args: Optional[tuple] = None
    kwargs: Optional[dict] = None
    return_value: Optional[Any] = None
    exception: Optional[Exception] = None
    stack_trace: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """获取span耗时（毫秒）"""
        end = self.end_time if self.end_time > 0 else time.time()
        return (end - self.start_time) * 1000

    def end(self) -> None:
        """结束span"""
        if self.end_time == 0.0:
            self.end_time = time.time()

    def set_exception(self, exc: Exception) -> None:
        """设置异常信息并记录堆栈"""
        self.exception = exc
        self.stack_trace = traceback.format_exc()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "module_name": self.module_name,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "class_name": self.class_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "args": repr(self.args) if self.args is not None else None,
            "kwargs": repr(self.kwargs) if self.kwargs is not None else None,
            "return_value": repr(self.return_value) if self.return_value is not None else None,
            "exception": repr(self.exception) if self.exception is not None else None,
            "stack_trace": self.stack_trace,
            "meta_data": self.meta_data
        }


def get_trace_id() -> str:
    """获取当前trace_id"""
    return trace_id_var.get()


def start_span(
    name: str,
    module_name: str,
    class_name: Optional[str] = None,
    meta_data: Optional[Dict[str, Any]] = None
) -> Span:
    """启动一个新的span"""
    span_stack = span_stack_var.get([])
    parent_span_id = span_stack[-1].span_id if span_stack else None

    # 如果没有trace_id，自动生成一个
    if not trace_id_var.get():
        trace_id_var.set(uuid.uuid4().hex)

    span = Span(
        name=name,
        module_name=module_name,
        class_name=class_name,
        parent_span_id=parent_span_id,
        meta_data=meta_data or {}
    )

    span_stack.append(span)
    span_stack_var.set(span_stack)

    return span


def end_span(span: Span) -> None:
    """结束span，如果是当前栈顶则弹出"""
    span.end()
    span_stack = span_stack_var.get([])

    if span_stack and span_stack[-1] is span:
        span_stack.pop()
        span_stack_var.set(span_stack)


def get_current_span() -> Optional[Span]:
    """获取当前活跃的span（栈顶）"""
    span_stack = span_stack_var.get([])
    return span_stack[-1] if span_stack else None


def get_root_span() -> Optional[Span]:
    """获取根span（栈底）"""
    span_stack = span_stack_var.get([])
    return span_stack[0] if span_stack else None


def get_all_spans() -> List[Span]:
    """获取当前链路的所有span"""
    return span_stack_var.get([]).copy()


def clear_context() -> None:
    """清空上下文"""
    trace_id_var.set("")
    span_stack_var.set([])
