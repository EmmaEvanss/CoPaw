# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Tests for MCP call_tool per-notification timeout refresh."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.swe.app.mcp.stateful_client import (
    _call_with_timeout_refresh,
)


# ---------------------------------------------------------------------------
# _call_with_timeout_refresh unit tests
# ---------------------------------------------------------------------------


class TestCallWithTimeoutRefreshNotificationRefresh:
    """Progress notification resets timeout; tool completes successfully."""

    @pytest.mark.asyncio
    async def test_notification_refresh_and_completion(self):
        """Simulate notifications at 0.05s intervals, tool completes at 0.2s."""
        progress_event = asyncio.Event()

        async def tool_coro():
            await asyncio.sleep(0.2)
            return "done"

        async def send_notifications():
            for _ in range(4):
                await asyncio.sleep(0.05)
                progress_event.set()

        tool_task = asyncio.ensure_future(
            _call_with_timeout_refresh(
                tool_coro(),
                per_notification_timeout=0.15,
                max_total_timeout=None,
                operation="call_tool(test)",
                client_name="test-client",
                progress_event=progress_event,
            ),
        )
        notif_task = asyncio.ensure_future(send_notifications())

        result = await tool_task
        await notif_task
        assert result == "done"


class TestCallWithTimeoutRefreshNoNotification:
    """No notification within per_notification_timeout raises TimeoutError."""

    @pytest.mark.asyncio
    async def test_no_notification_timeout(self):
        progress_event = asyncio.Event()

        async def tool_coro():
            await asyncio.sleep(10)  # would never complete
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await _call_with_timeout_refresh(
                tool_coro(),
                per_notification_timeout=0.1,
                max_total_timeout=None,
                operation="call_tool(test)",
                client_name="test-client",
                progress_event=progress_event,
            )


class TestCallWithTimeoutRefreshFallback:
    """No progress_event → falls back to _call_with_timeout."""

    @pytest.mark.asyncio
    async def test_fallback_no_progress_event(self):
        async def tool_coro():
            return "done"

        result = await _call_with_timeout_refresh(
            tool_coro(),
            per_notification_timeout=0.1,
            max_total_timeout=None,
            operation="call_tool(test)",
            client_name="test-client",
            progress_event=None,
        )
        assert result == "done"

    @pytest.mark.asyncio
    async def test_fallback_timeout(self):
        async def tool_coro():
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await _call_with_timeout_refresh(
                tool_coro(),
                per_notification_timeout=0.1,
                max_total_timeout=None,
                operation="call_tool(test)",
                client_name="test-client",
                progress_event=None,
            )


class TestCallWithTimeoutRefreshMaxTotal:
    """max_total_timeout ceiling cancels call despite ongoing notifications."""

    @pytest.mark.asyncio
    async def test_max_total_exceeded(self):
        progress_event = asyncio.Event()

        async def tool_coro():
            await asyncio.sleep(10)
            return "done"

        async def send_notifications():
            # Send notifications faster than per_notification_timeout
            # to prevent per-frame timeout, but max_total will trigger
            for _ in range(20):
                await asyncio.sleep(0.03)
                progress_event.set()

        tool_task = asyncio.ensure_future(
            _call_with_timeout_refresh(
                tool_coro(),
                per_notification_timeout=0.2,
                max_total_timeout=0.15,
                operation="call_tool(test)",
                client_name="test-client",
                progress_event=progress_event,
            ),
        )
        notif_task = asyncio.ensure_future(send_notifications())

        with pytest.raises(asyncio.TimeoutError):
            await tool_task
        await notif_task


class TestCallWithTimeoutRefreshTaskDoneBeforeNotification:
    """Tool completes before any notification; task.done() check at loop top."""

    @pytest.mark.asyncio
    async def test_task_completes_immediately(self):
        progress_event = asyncio.Event()

        async def tool_coro():
            return "instant"

        result = await _call_with_timeout_refresh(
            tool_coro(),
            per_notification_timeout=5.0,
            max_total_timeout=None,
            operation="call_tool(test)",
            client_name="test-client",
            progress_event=progress_event,
        )
        assert result == "instant"


class TestProgressCallbacksInjectionCleanup:
    """_progress_callbacks injection and cleanup on success, timeout, and
    cancellation."""

    def _make_session_mock(self):
        session = MagicMock()
        session._progress_callbacks = {}
        session.call_tool = AsyncMock(
            return_value=MagicMock(content=[], meta={}),
        )
        return session

    @pytest.mark.asyncio
    async def test_cleanup_on_success(self):
        """Callback injected during call, removed after success."""
        from src.swe.app.mcp.stateful_client import StdIOStatefulClient

        session = self._make_session_mock()
        client = StdIOStatefulClient.__new__(StdIOStatefulClient)
        client.name = "test"
        client.session = session
        client.is_connected = True
        client.on_progress_callback = None
        client._validate_connection = MagicMock()

        meta = {"progressToken": "test@abc-123"}

        with patch(
            "src.swe.app.mcp.stateful_client.MCP_PER_NOTIFICATION_TIMEOUT",
            0.1,
        ), patch(
            "src.swe.app.mcp.stateful_client.MCP_MAX_TOTAL_TIMEOUT",
            0.0,
        ):
            await client.call_tool("my_tool", meta=meta)

        # Callback must be cleaned up
        assert "test@abc-123" not in session._progress_callbacks

    @pytest.mark.asyncio
    async def test_cleanup_on_timeout(self):
        """Callback removed after timeout."""
        from src.swe.app.mcp.stateful_client import StdIOStatefulClient

        session = self._make_session_mock()

        # Make call_tool hang forever
        async def _hang(*_a, **_kw):
            await asyncio.sleep(100)

        session.call_tool = AsyncMock(side_effect=_hang)

        client = StdIOStatefulClient.__new__(StdIOStatefulClient)
        client.name = "test"
        client.session = session
        client.is_connected = True
        client.on_progress_callback = None
        client._validate_connection = MagicMock()

        meta = {"progressToken": "test@timeout-123"}

        with patch(
            "src.swe.app.mcp.stateful_client.MCP_PER_NOTIFICATION_TIMEOUT",
            0.05,
        ), patch(
            "src.swe.app.mcp.stateful_client.MCP_MAX_TOTAL_TIMEOUT",
            0.0,
        ):
            with pytest.raises(asyncio.TimeoutError):
                await client.call_tool("my_tool", meta=meta)

        assert "test@timeout-123" not in session._progress_callbacks

    @pytest.mark.asyncio
    async def test_no_injection_without_progress_token(self):
        """No callback injection when meta has no progressToken."""
        from src.swe.app.mcp.stateful_client import StdIOStatefulClient

        session = self._make_session_mock()
        client = StdIOStatefulClient.__new__(StdIOStatefulClient)
        client.name = "test"
        client.session = session
        client.is_connected = True
        client.on_progress_callback = None
        client._validate_connection = MagicMock()

        with patch(
            "src.swe.app.mcp.stateful_client.MCP_PER_NOTIFICATION_TIMEOUT",
            0.1,
        ), patch(
            "src.swe.app.mcp.stateful_client.MCP_MAX_TOTAL_TIMEOUT",
            0.0,
        ):
            await client.call_tool("my_tool")

        assert len(session._progress_callbacks) == 0


class TestOnProgressCallback:
    """on_progress_callback is invoked when progress notifications arrive."""

    @pytest.mark.asyncio
    async def test_callback_invoked_on_notification(self):
        """on_progress_callback is called each time progress_event is set."""
        progress_event = asyncio.Event()
        callback_calls = []

        def my_callback():
            callback_calls.append(True)

        async def tool_coro():
            await asyncio.sleep(0.2)
            return "done"

        async def send_notifications():
            for _ in range(3):
                await asyncio.sleep(0.05)
                progress_event.set()

        tool_task = asyncio.ensure_future(
            _call_with_timeout_refresh(
                tool_coro(),
                per_notification_timeout=0.15,
                max_total_timeout=None,
                operation="call_tool(test)",
                client_name="test-client",
                progress_event=progress_event,
                on_progress_callback=my_callback,
            ),
        )
        notif_task = asyncio.ensure_future(send_notifications())

        result = await tool_task
        await notif_task
        assert result == "done"
        assert len(callback_calls) >= 1

    @pytest.mark.asyncio
    async def test_no_callback_when_none(self):
        """When on_progress_callback is None, progress works normally."""
        progress_event = asyncio.Event()

        async def tool_coro():
            await asyncio.sleep(0.1)
            return "done"

        async def send_notifications():
            await asyncio.sleep(0.03)
            progress_event.set()

        tool_task = asyncio.ensure_future(
            _call_with_timeout_refresh(
                tool_coro(),
                per_notification_timeout=0.15,
                max_total_timeout=None,
                operation="call_tool(test)",
                client_name="test-client",
                progress_event=progress_event,
                on_progress_callback=None,
            ),
        )
        notif_task = asyncio.ensure_future(send_notifications())

        result = await tool_task
        await notif_task
        assert result == "done"

    @pytest.mark.asyncio
    async def test_client_on_progress_callback_in_call_tool(self):
        """StdIOStatefulClient.on_progress_callback is called from _on_progress."""
        from src.swe.app.mcp.stateful_client import StdIOStatefulClient

        session = MagicMock()
        session._progress_callbacks = {}
        session.call_tool = AsyncMock(
            return_value=MagicMock(content=[], meta={}),
        )

        client = StdIOStatefulClient.__new__(StdIOStatefulClient)
        client.name = "test"
        client.session = session
        client.is_connected = True
        client.on_progress_callback = None
        client._validate_connection = MagicMock()
        callback_calls = []
        client.on_progress_callback = lambda: callback_calls.append(True)

        meta = {"progressToken": "test@cb-123"}

        with patch(
            "src.swe.app.mcp.stateful_client.MCP_PER_NOTIFICATION_TIMEOUT",
            0.1,
        ), patch(
            "src.swe.app.mcp.stateful_client.MCP_MAX_TOTAL_TIMEOUT",
            0.0,
        ):
            # Simulate a progress notification after a short delay
            async def _call_and_notify(*_a, **_kw):
                # Manually trigger the injected callback
                cb = session._progress_callbacks.get("test@cb-123")
                if cb:
                    await cb(0.5, 1.0, "progress")
                return MagicMock(content=[], meta={})

            session.call_tool = AsyncMock(side_effect=_call_and_notify)
            await client.call_tool("my_tool", meta=meta)

        assert len(callback_calls) >= 1


# ---------------------------------------------------------------------------
# _wire_mcp_progress_callbacks: bound method __self__ extraction
# ---------------------------------------------------------------------------


class TestWireMcpProgressCallbacksBoundMethod:
    """_wire_mcp_progress_callbacks must extract the MCPToolFunction instance
    from the bound method stored in original_func."""

    def _make_agent_mock(self, tools_dict):
        """Build a minimal mock agent with a toolkit containing the given
        tools dict (name -> RegisteredToolFunction-like object)."""
        agent = MagicMock()
        agent.toolkit = MagicMock()
        agent.toolkit.tools = tools_dict
        agent._reset_watchdog = MagicMock()
        return agent

    def _wire(self, agent, client_name):
        """Invoke _wire_mcp_progress_callbacks without importing ReactAgent
        (which has heavy transitive dependencies)."""
        from agentscope.mcp._mcp_function import MCPToolFunction

        cb = agent._reset_watchdog
        mcp_name = client_name
        for tool_entry in agent.toolkit.tools.values():
            func = getattr(tool_entry, "original_func", None)
            if func is None:
                continue
            mcp_func = getattr(func, "__self__", None) or func
            if (
                isinstance(mcp_func, MCPToolFunction)
                and mcp_func.mcp_name == mcp_name
            ):
                mcp_func.on_progress_callback = cb

    def test_sets_callback_on_mcp_tool_via_self(self):
        """original_func is a bound method; __self__ yields the MCPToolFunction
        instance, and on_progress_callback is set on that instance."""
        from agentscope.mcp._mcp_function import MCPToolFunction

        mcp_func = MCPToolFunction.__new__(MCPToolFunction)
        mcp_func.mcp_name = "my-server"
        mcp_func.name = "search"

        # Simulate what AgentScope stores: original_func = tool_func.__call__
        tool_entry = MagicMock()
        tool_entry.original_func = mcp_func.__call__  # bound method

        agent = self._make_agent_mock({"search": tool_entry})
        self._wire(agent, "my-server")

        assert mcp_func.on_progress_callback is agent._reset_watchdog

    def test_skips_non_mcp_tools(self):
        """original_func for a regular function is not a bound method of
        MCPToolFunction; it should be skipped without error."""
        tool_entry = MagicMock()

        def plain_func(**_kwargs):
            pass

        tool_entry.original_func = plain_func

        agent = self._make_agent_mock({"plain": tool_entry})
        self._wire(agent, "my-server")

        assert not hasattr(plain_func, "on_progress_callback")

    def test_skips_wrong_mcp_name(self):
        """MCPToolFunction belonging to a different server is skipped."""
        from agentscope.mcp._mcp_function import MCPToolFunction

        mcp_func = MCPToolFunction.__new__(MCPToolFunction)
        mcp_func.mcp_name = "other-server"
        mcp_func.name = "search"

        tool_entry = MagicMock()
        tool_entry.original_func = mcp_func.__call__

        agent = self._make_agent_mock({"search": tool_entry})
        self._wire(agent, "my-server")

        assert not hasattr(mcp_func, "on_progress_callback")

    def test_skips_none_original_func(self):
        """original_func being None does not cause an error."""
        tool_entry = MagicMock()
        tool_entry.original_func = None

        agent = self._make_agent_mock({"broken": tool_entry})
        # Should not raise
        self._wire(agent, "my-server")
