"""Context manager to temporarily bind logging context."""

import structlog


class LogContext:
    """Context manager for adding temporary log context."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        structlog.contextvars.bind_contextvars(**self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        structlog.contextvars.clear_contextvars()

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)
