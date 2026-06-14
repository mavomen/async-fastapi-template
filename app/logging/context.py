"""Context manager to temporarily bind logging context."""

from types import TracebackType
from typing import Any

import structlog


class LogContext:
    """Context manager for adding temporary log context."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self._keys: list[str] = []

    def __enter__(self) -> "LogContext":
        self._keys = list(self.kwargs)
        structlog.contextvars.bind_contextvars(**self.kwargs)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        structlog.contextvars.unbind_contextvars(*self._keys)

    async def __aenter__(self) -> "LogContext":
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)
