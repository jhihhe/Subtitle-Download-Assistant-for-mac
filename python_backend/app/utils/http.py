"""MoviePilot app.utils.http 的最小独立存根，基于 httpx 实现。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx


class _Response:
    """兼容 MoviePilot 响应对象的包装。"""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> httpx.Headers:
        return self._response.headers

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def text(self) -> str:
        return self._response.text

    def json(self) -> Any:
        return self._response.json()

    async def aiter_bytes(self, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        async for chunk in self._response.aiter_bytes(chunk_size):
            yield chunk


class AsyncRequestUtils:
    """最小异步 HTTP 客户端，覆盖本项目实际使用的方法。"""

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        proxies: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> None:
        self._headers = headers or {}
        proxy = proxies.get("https") or proxies.get("http") if proxies else None
        self._client = httpx.AsyncClient(
            headers=self._headers,
            proxy=proxy,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def get_res(self, url: str, **kwargs: Any) -> _Response | None:
        try:
            response = await self._client.get(url, **kwargs)
            return _Response(response)
        except Exception:
            return None

    async def post_res(self, url: str, **kwargs: Any) -> _Response | None:
        try:
            response = await self._client.post(url, **kwargs)
            return _Response(response)
        except Exception:
            return None

    @asynccontextmanager
    async def get_stream(self, url: str) -> AsyncIterator[_Response]:
        async with self._client.stream("GET", url) as response:
            yield _Response(response)

    async def aclose(self) -> None:
        await self._client.aclose()
