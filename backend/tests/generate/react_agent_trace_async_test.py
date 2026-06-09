import asyncio
import concurrent.futures
import logging

from backend.v1.app.agent.implementations import react_agent as react_agent_module


def test_save_trace_logs_background_future_exception(monkeypatch, caplog):
    class _RunningLoop:
        def is_running(self):
            return True

    agent = object.__new__(react_agent_module.ReActAgent)
    agent.tracing_config = {"enabled": True, "async_save": True}
    agent._loop = _RunningLoop()
    agent.model = "test-model"
    agent.model_config = {"temperature": 0, "max_tokens": 0, "top_p": 1}

    monkeypatch.setattr(react_agent_module, "HAS_TRACE_STORAGE", True)

    async def fake_save_trace_async(**kwargs):
        return None

    agent._save_trace_async = fake_save_trace_async

    future = concurrent.futures.Future()
    future.set_exception(RuntimeError("trace boom"))

    def fake_run_coroutine_threadsafe(coro, loop):
        coro.close()
        return future

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    with caplog.at_level(logging.WARNING):
        agent._save_trace(
            session_id="session-1",
            user_input="user input",
            system_prompt="system prompt",
            messages_history=[],
            iterations=1,
            all_tool_calls=[],
            all_tool_results=[],
            final_answer="answer",
        )

    assert "Agent" in caplog.text
    assert "trace boom" in caplog.text
