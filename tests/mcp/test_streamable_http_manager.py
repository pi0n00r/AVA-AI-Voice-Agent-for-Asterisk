import asyncio

from src.config import MCPConfig, MCPServerConfig
from src.mcp.manager import MCPClientManager
from src.mcp.streamable_http_client import MCPStreamableHttpClient


def test_manager_builds_streamable_http_client(monkeypatch):
    calls = []

    async def fake_start(self):
        calls.append((self.server_id, self.url, dict(self.headers)))

    async def fake_list_tools(self):
        return [
            {
                "name": "health",
                "description": "Health",
                "inputSchema": {"type": "object"},
            }
        ]

    async def fake_stop(self):
        return None

    monkeypatch.setattr(MCPStreamableHttpClient, "start", fake_start)
    monkeypatch.setattr(MCPStreamableHttpClient, "list_tools", fake_list_tools)
    monkeypatch.setattr(MCPStreamableHttpClient, "stop", fake_stop)

    config = MCPConfig(
        enabled=True,
        servers={
            "isla": MCPServerConfig(
                transport="streamable-http",
                url="https://isla.example/mcp/codex",
                headers={"Authorization": "Bearer fixture"},
            )
        },
    )
    manager = MCPClientManager(config)
    asyncio.run(manager.start())

    assert calls == [
        ("isla", "https://isla.example/mcp/codex", {"Authorization": "Bearer fixture"})
    ]
    status = manager.get_status()
    assert status["servers"]["isla"]["up"] is True
    assert status["servers"]["isla"]["transport"] == "streamable-http"
    assert "headers" not in status["servers"]["isla"]
    asyncio.run(manager.stop())
