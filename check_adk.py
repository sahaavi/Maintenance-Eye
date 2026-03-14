import asyncio

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService


async def check_event_structure():
    agent = Agent(name="test", model="gemini-2.5-flash", tools=[])
    runner = Runner(app_name="test", agent=agent, session_service=InMemorySessionService())

    # We can't actually run it without an API key, but we can look at the type hints if available
    # or just look at the code of the Runner
    import inspect

    print(f"Runner.run_live signature: {inspect.signature(runner.run_live)}")

    # Try to find the event class
    from google.adk.agents.runner import StreamingEvent

    print(f"StreamingEvent fields: {StreamingEvent.__annotations__}")


if __name__ == "__main__":
    asyncio.run(check_event_structure())
