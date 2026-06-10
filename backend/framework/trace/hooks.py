"""
Trace生命周期钩子机制
提供标准化的扩展点，支持在trace的各个生命周期节点注入自定义行为
"""
from typing import Callable, Optional, Any
from dataclasses import dataclass
from .context import Span
@dataclass
class TraceHooks:
    """
    Trace生命周期钩子集合
    所有钩子函数都是可选的，未提供则不执行
    """
    # 函数执行开始时调用，参数为当前span
    on_start: Optional[Callable[[Span], None]] = None

    # 函数执行成功结束时调用，参数为当前span
    on_end: Optional[Callable[[Span], None]] = None

    # 函数执行发生异常时调用，参数为当前span和异常对象
    on_error: Optional[Callable[[Span, Exception], None]] = None
    @classmethod
    def merge(cls, *hooks_list: Optional["TraceHooks"]) -> "TraceHooks":
        """
        合并多个钩子集合
        相同类型的钩子会按顺序依次执行
        """
        merged = cls()

        for hooks in hooks_list:
            if not hooks:
                continue

            # 合并on_start钩子
            if hooks.on_start:
                if merged.on_start:
                    existing = merged.on_start
                    new_hook = hooks.on_start
                    merged.on_start = lambda span: (existing(span), new_hook(span))
                else:
                    merged.on_start = hooks.on_start

            # 合并on_end钩子
            if hooks.on_end:
                if merged.on_end:
                    existing = merged.on_end
                    new_hook = hooks.on_end
                    merged.on_end = lambda span: (existing(span), new_hook(span))
                else:
                    merged.on_end = hooks.on_end

            # 合并on_error钩子
            if hooks.on_error:
                if merged.on_error:
                    existing = merged.on_error
                    new_hook = hooks.on_error
                    merged.on_error = lambda span, exc: (existing(span, exc), new_hook(span, exc))
                else:
                    merged.on_error = hooks.on_error

        return merged
