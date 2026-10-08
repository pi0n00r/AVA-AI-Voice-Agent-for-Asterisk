# Fleet MCP servers

AVA can connect directly to fleet Streamable HTTP MCP servers. Authentication
headers retain their environment references until the MCP client resolves them
for each operation. Credentials must remain in the protected
deployment environment, never in YAML, logs, source, or Admin UI receipts.

```yaml
mcp:
  enabled: true
  servers:
    bridgette:
      transport: streamable-http
      url: https://bridgette.bajaj.com/mcp
      defaults: {timeout_ms: 15000}
    isla:
      transport: streamable-http
      url: https://isla.bajaj.com/mcp/codex
      headers:
        Authorization: "Bearer ${ISLA_AUTH_TOKEN}"
      defaults: {timeout_ms: 15000}
    notes:
      transport: streamable-http
      url: https://notes.bajaj.com/mcp
      headers:
        Authorization: "Bearer ${TRILIUM_ETAPI_TOKEN}"
      defaults: {timeout_ms: 15000}
    n8n:
      transport: streamable-http
      url: https://booltool.bajaj.com/mcp-server/http
      headers:
        Authorization: "Bearer ${N8N_MCP_SERVER_API_KEY}"
      defaults: {timeout_ms: 15000}
```

The SDK-backed HTTP client negotiates the current MCP protocol, accepts JSON and
SSE responses, and owns a fresh session per operation. It rejects an SSE reply
whose JSON-RPC ID does not match the request and does not replay an
unknown-result tool call. Discovery/setup failures before `tools/call` are
reported as not invoked, not unknown. The existing `streamable-http` configuration spelling
remains supported alongside `streamable_http`. URLs reject embedded credentials
and query data; configured headers are not reported, and redirects are refused.
The protected YAML loader preserves header templates while expanding other
configuration fields. Every configured custom header must be an entire
environment reference; Authorization may prefix that reference with an HTTP
scheme. Literal headers and defaults such as `${TOKEN:-literal}` are rejected,
including through the manager path. SDK
message/session logs are suppressed; AVA retains only metadata-only failure
diagnostics.

MCP tools remain in-call tools. Global discovery does not expose a tool to a
caller: select provider-safe `mcp_<server>_<tool>` names explicitly on the
intended Agent. Keep the public Extn 7 receptionist limited to its established
transfer/message-taking surface. Assign fleet MCP tools only to the private
operator-facing Extn 6 Agent after catalog review and synthetic validation.

## Production acceptance

1. Validate protected environment and YAML without printing values.
2. Prove all four servers return non-empty catalogs from `ai_engine`.
3. Confirm `/mcp/status` contains no headers or tokens.
4. Confirm Extn 7 Agent tools are byte/semantic unchanged.
5. Restart only `ai_engine` at zero active calls.
6. Read back source hashes, status, catalogs, and Agent assignments.
