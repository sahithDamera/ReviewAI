import asyncio
import sys


def event_loop_factory() -> asyncio.AbstractEventLoop:
    """Psycopg async requires a selector loop on Windows."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()
