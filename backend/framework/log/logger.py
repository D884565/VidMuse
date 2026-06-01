"""结构化 JSON 日志器，自动注入链路信息"""
import logging
import json
import sys
from datetime import datetime

from backend.trace import get_trace_id, span_stack_var


class TraceFormatter(logging.Formatter):
    """输出带 request_id + 当前 span 路径的结构化 JSON 日志"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "request_id": get_request_id(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 附带当前调用链路径
        stack = span_stack_var.get()
        if stack:
            log_data["trace"] = " > ".join(s.name for s in stack)

        if record.exc_info and record.exc_info[1] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """初始化全局日志配置，项目启动时调用一次"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(TraceFormatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]
