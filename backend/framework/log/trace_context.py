"""基于 ContextVar 的请求链路上下文管理"""
import contextvars
import time
from dataclasses import dataclass, field

# 请求级上下文变量
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
span_stack_var: contextvars.ContextVar[list] = contextvars.ContextVar("span_stack", default=[])


@dataclass
class Span:
    """调用链节点"""
    name: str
    start: float = field(default_factory=time.time)
    end: float = 0.0
    children: list = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end == 0.0:
            return (time.time() - self.start) * 1000
        return (self.end - self.start) * 1000

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 2),
            "children": [child.to_dict() for child in self.children],
        }


def get_request_id() -> str:
    """获取当前请求的 request_id"""
    return request_id_var.get()


def start_span(name: str) -> Span:
    """开始一个新的 span，压入调用栈"""
    stack = span_stack_var.get()
    span = Span(name=name)
    if stack:
        stack[-1].children.append(span)
    stack.append(span)
    span_stack_var.set(stack)
    return span


def end_span(span: Span) -> None:
    """结束一个 span，弹出调用栈"""
    span.end = time.time()
    stack = span_stack_var.get()
    if stack and stack[-1] is span:
        stack.pop()


def get_root_span() -> Span | None:
    """获取当前调用栈的根 span"""
    stack = span_stack_var.get()
    return stack[0] if stack else None
