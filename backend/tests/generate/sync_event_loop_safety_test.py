from types import SimpleNamespace

from backend.framework.trace import trace
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.pipeline import BasePipeline
from backend.v1.app.pipeline.base.processor import BaseProcessor


class _NoopProcessor(BaseProcessor):
    def process(self, context: PipelineContext) -> PipelineContext:
        context.set("processed", True)
        return context


class _FakeDB:
    def close(self):
        return None


def test_sync_trace_function_does_not_require_running_event_loop(monkeypatch):
    async def fake_add_to_batch(_span):
        return None

    monkeypatch.setattr("backend.framework.trace.decorator.add_to_batch", fake_add_to_batch)

    @trace
    def traced_sum(left: int, right: int) -> int:
        return left + right

    assert traced_sum(2, 3) == 5


def test_sync_pipeline_persistence_does_not_require_running_event_loop(monkeypatch):
    pipeline = BasePipeline(processors=[_NoopProcessor()], enable_persistence=True)

    async def fake_status_change(_execution_id: str):
        return None

    monkeypatch.setattr(
        "backend.framework.trace.decorator.add_to_batch",
        fake_status_change,
    )
    monkeypatch.setattr(
        "backend.v1.app.pipeline.base.pipeline.get_db",
        lambda: iter([_FakeDB()]),
    )
    monkeypatch.setattr(
        "backend.v1.app.pipeline.base.pipeline.PipelineExecutionDAO.create_execution",
        lambda *args, **kwargs: SimpleNamespace(execution_id="exec-sync-1"),
    )
    monkeypatch.setattr(
        "backend.v1.app.pipeline.base.pipeline.PipelineExecutionDAO.update_execution_status",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "backend.v1.app.pipeline.base.pipeline.PipelineExecutionDAO.update_execution_progress",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "backend.v1.app.pipeline.base.pipeline.PipelineExecutionDAO.update_execution_result",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(pipeline, "_on_status_change", fake_status_change)

    result = pipeline.run_with_persistence({"asset_id": 11})

    assert result["success"] is True
    assert result["data"]["processed"] is True
    assert result["execution_id"] == "exec-sync-1"
