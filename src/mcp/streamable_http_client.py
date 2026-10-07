from __future__ import annotations

import json
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp
import structlog

from .errors import MCPError, MCPProtocolError, MCPServerExited

logger = structlog.get_logger(__name__)


class MCPStreamableHttpClient:
    """Minimal MCP Streamable HTTP client with session reconciliation."""

    def __init__(
        self,
        *,
        server_id: str,
        url: str,
        headers: Dict[str, str],
        default_timeout_ms: int = 10000,
    ):
        self.server_id = server_id
        self.url = str(url or "").strip()
        self.headers = {str(k): str(v) for k, v in (headers or {}).items()}
        self.default_timeout_ms = int(default_timeout_ms)
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_id: Optional[str] = None
        self._next_id = 1
        self._initialized = False
        self._closing = False
        self._validate_url()

    def _validate_url(self) -> None:
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise MCPError(f"MCP server '{self.server_id}' has an invalid HTTP URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise MCPError(
                f"MCP server '{self.server_id}' URL must not contain credentials, "
                "query, or fragment"
            )

    async def start(self) -> None:
        await self._ensure_session()
        await self.initialize()

    async def stop(self) -> None:
        self._closing = True
        session = self._session
        self._session = None
        self._initialized = False
        if session and not session.closed:
            await session.close()

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self._ensure_session()
        await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Asterisk-AI-Voice-Agent", "version": "dev"},
            },
            _skip_initialize=True,
        )
        self._initialized = True
        await self.notify("notifications/initialized", {})

    async def list_tools(self) -> List[Dict[str, Any]]:
        await self.initialize()
        result = await self.request("tools/list", {})
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    async def call_tool(
        self,
        *,
        name: str,
        arguments: Dict[str, Any],
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        await self.initialize()
        return await self.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            timeout_ms=timeout_ms,
        )

    async def notify(self, method: str, params: Dict[str, Any]) -> None:
        await self._ensure_session()
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        await self._post(payload, timeout_ms=self.default_timeout_ms, notification=True)

    async def request(
        self,
        method: str,
        params: Dict[str, Any],
        timeout_ms: Optional[int] = None,
        *,
        _skip_initialize: bool = False,
    ) -> Dict[str, Any]:
        if not _skip_initialize:
            await self.initialize()
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        response = await self._post(
            payload,
            timeout_ms=self.default_timeout_ms
            if timeout_ms is None
            else int(timeout_ms),
            notification=False,
        )
        if not isinstance(response, dict):
            raise MCPProtocolError(
                f"Invalid MCP response type: {type(response).__name__}"
            )
        if response.get("id") not in {request_id, str(request_id)}:
            raise MCPProtocolError("MCP response ID did not match the request")
        if response.get("error"):
            raise MCPError(str(response["error"]))
        result = response.get("result")
        return result if isinstance(result, dict) else {"value": result}

    async def _ensure_session(self) -> None:
        if self._closing:
            raise MCPServerExited(f"MCP server '{self.server_id}' is shutting down")
        if self._session and not self._session.closed:
            return
        connector = aiohttp.TCPConnector(
            family=socket.AF_UNSPEC,
            happy_eyeballs_delay=0.25,
        )
        self._session = aiohttp.ClientSession(connector=connector)

    def _request_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        headers.update(self.headers)
        if self._session_id:
            headers["MCP-Session-Id"] = self._session_id
        return headers

    async def _post(
        self,
        payload: Dict[str, Any],
        *,
        timeout_ms: int,
        notification: bool,
    ) -> Optional[Dict[str, Any]]:
        await self._ensure_session()
        if not self._session:
            raise MCPServerExited(
                f"MCP server '{self.server_id}' HTTP client is unavailable"
            )
        timeout = aiohttp.ClientTimeout(total=max(0.001, float(timeout_ms) / 1000.0))
        try:
            async with self._session.post(
                self.url,
                json=payload,
                headers=self._request_headers(),
                timeout=timeout,
                allow_redirects=False,
            ) as response:
                if response.status in {202, 204} and notification:
                    return None
                if response.status < 200 or response.status >= 300:
                    raise MCPError(
                        f"MCP server '{self.server_id}' returned HTTP {response.status}"
                    )
                new_session_id = response.headers.get("MCP-Session-Id")
                if new_session_id:
                    self._session_id = new_session_id
                body = await response.text()
                if notification and not body.strip():
                    return None
                return self._decode_response(body, response.content_type)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise MCPError(
                f"MCP server '{self.server_id}' request failed: {type(exc).__name__}"
            ) from exc

    @staticmethod
    def _decode_response(body: str, content_type: str) -> Dict[str, Any]:
        if content_type == "text/event-stream" or body.lstrip().startswith(
            ("event:", "data:")
        ):
            events: List[Dict[str, Any]] = []
            data_lines: List[str] = []
            for line in body.splitlines() + [""]:
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif line == "" and data_lines:
                    try:
                        value = json.loads("\n".join(data_lines))
                    except json.JSONDecodeError as exc:
                        raise MCPProtocolError(
                            "Invalid JSON in MCP SSE response"
                        ) from exc
                    if isinstance(value, dict):
                        events.append(value)
                    data_lines = []
            if not events:
                raise MCPProtocolError("MCP SSE response contained no JSON-RPC event")
            return events[-1]
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MCPProtocolError("Invalid JSON in MCP HTTP response") from exc
        if not isinstance(value, dict):
            raise MCPProtocolError("MCP HTTP response was not a JSON object")
        return value
