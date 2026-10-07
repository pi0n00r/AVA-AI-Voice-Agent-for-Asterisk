import asyncio
import socket

from aiohttp import web

from src.mcp.streamable_http_client import MCPStreamableHttpClient


def test_streamable_http_initialize_discovery_call_and_session_header():
    async def scenario():
        seen = []

        async def handler(request):
            payload = await request.json()
            seen.append(
                (
                    payload,
                    request.headers.get("MCP-Session-Id"),
                    request.headers.get("Authorization"),
                )
            )
            method = payload["method"]
            if method == "initialize":
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": payload["id"],
                        "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
                    },
                    headers={"MCP-Session-Id": "session-1"},
                )
            if method == "notifications/initialized":
                return web.Response(status=202)
            if method == "tools/list":
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": payload["id"],
                        "result": {
                            "tools": [
                                {
                                    "name": "lookup",
                                    "description": "Lookup",
                                    "inputSchema": {"type": "object"},
                                }
                            ]
                        },
                    }
                )
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"content": [{"type": "text", "text": "ok"}]},
                }
            )

        app = web.Application()
        app.router.add_post("/mcp", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        sock.bind(("::1", 0))
        sock.listen(128)
        site = web.SockSite(runner, sock)
        await site.start()

        client = MCPStreamableHttpClient(
            server_id="fixture",
            url=f"http://[::1]:{sock.getsockname()[1]}/mcp",
            headers={"Authorization": "Bearer fixture-secret"},
        )
        try:
            await client.start()
            tools = await client.list_tools()
            result = await client.call_tool(name="lookup", arguments={"q": "x"})
        finally:
            await client.stop()
            await runner.cleanup()

        assert [t["name"] for t in tools] == ["lookup"]
        assert result["content"][0]["text"] == "ok"
        assert seen[0][1] is None
        assert all(item[2] == "Bearer fixture-secret" for item in seen)
        assert all(item[1] == "session-1" for item in seen[1:])

    asyncio.run(scenario())


def test_streamable_http_decodes_sse_json_rpc():
    body = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n'
    decoded = MCPStreamableHttpClient._decode_response(body, "text/event-stream")
    assert decoded["result"] == {"tools": []}
