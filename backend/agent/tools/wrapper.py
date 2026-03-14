import asyncio
import functools
import logging

logger = logging.getLogger("maintenance-eye.tools.wrapper")

# Queue of tool results per session
# Map: session_id -> asyncio.Queue
_tool_result_queues: dict[str, asyncio.Queue] = {}


def get_tool_result_queue(session_id: str) -> asyncio.Queue:
    if session_id not in _tool_result_queues:
        _tool_result_queues[session_id] = asyncio.Queue()
    return _tool_result_queues[session_id]


def remove_tool_result_queue(session_id: str):
    _tool_result_queues.pop(session_id, None)


def tool_wrapper(func):
    """
    Decorator to wrap ADK tools and capture their results for the WebSocket side-channel.
    """

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        await _capture_result(result)
        return result

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        # We can't await here, so we use a task
        asyncio.create_task(_capture_result(result))
        return result

    async def _capture_result(result):
        # Import here to avoid circular imports
        from agent.tools.confirm_action import _get_session_context

        session_id = _get_session_context()
        if session_id and session_id != "default":
            queue = get_tool_result_queue(session_id)
            await queue.put(result)
            logger.debug(f"Captured tool result for session {session_id}")

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
