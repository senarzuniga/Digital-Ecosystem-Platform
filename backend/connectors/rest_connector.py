"""
REST Connector — generic HTTP client for ERP, CRM and third-party integrations.
Uses httpx for async HTTP with retry logic and auth support.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


class RestConnector:
    """
    Async REST client with:
      - Bearer token auth
      - Automatic retry with exponential back-off
      - Request/response logging

    Usage:
        connector = RestConnector(base_url="https://erp.example.com/api", token="xxx")
        data = await connector.get("/customers/C001")
        await connector.post("/invoices", json={"amount": 100})
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if api_key:
            headers[api_key_header] = api_key

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: Optional[dict] = None) -> Any:
        return await self._request("POST", path, json=json)

    async def put(self, path: str, json: Optional[dict] = None) -> Any:
        return await self._request("PUT", path, json=json)

    async def patch(self, path: str, json: Optional[dict] = None) -> Any:
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self._request("DELETE", path)

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        import asyncio

        url = path if path.startswith("http") else f"{self._base_url}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
                response.raise_for_status()
                logger.debug("%s %s → %d", method, url, response.status_code)
                return response.json() if response.content else None
            except httpx.HTTPStatusError as exc:
                logger.warning("%s %s → HTTP %d: %s", method, url, exc.response.status_code, exc.response.text[:200])
                raise
            except httpx.RequestError as exc:
                last_exc = exc
                wait = 2 ** (attempt - 1)
                logger.warning("%s %s failed (attempt %d/%d): %s. Retrying in %ds", method, url, attempt, MAX_RETRIES, exc, wait)
                await asyncio.sleep(wait)
        raise last_exc or RuntimeError("Request failed after retries")

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
