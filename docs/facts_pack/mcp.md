# FACTS_PACK: MCP (Model Context Protocol)

As of **2026-11-06**. Installed in a throwaway venv (`uv venv /tmp/facts_mcp`, CPython 3.13.5):
`mcp 2.3.0` (+ `mcp-types 2.3.0`), `fastmcp 4.1.6`, `openai 3.46.0`, `httpx2 2.16.0`, `pydantic 2.14.3`.
No live API calls were made. "Introspection" means `inspect.signature` or the installed source.
"Run" means the code was executed locally: in-memory, as a stdio subprocess, or over localhost HTTP.

## 2. VERIFIED API SHAPES
Install: `uv add "mcp[cli]"` (`[cli]` adds the `mcp` command). Docs: **Python 3.11+** (PyPI says `>=3.10`; teach 3.11+). v2 uses **`httpx2`**, not `httpx`.

### 2.1 Server: `MCPServer` (v2 name for FastMCP); tools, resources, prompts
```python
from mcp.server import MCPServer          # also: from mcp.server.mcpserver import MCPServer, Context
from mcp.types import ToolAnnotations

mcp = MCPServer("atlas-docs", version="0.1.0", instructions="Search Atlas docs.")

@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def search_docs(query: str, k: int = 3) -> list[str]:
    """Search the docs and return the top-k titles."""   # docstring -> tool description
    return [f"doc about {query} #{i}" for i in range(k)]

@mcp.resource("docs://{doc_id}")                      # {param} -> resource *template*
def get_doc(doc_id: str) -> str:
    return f"text of {doc_id}"

@mcp.prompt()
def summarize(topic: str) -> str:
    return f"Summarize what the docs say about {topic}."
```
verified by: introspection + run; the in-memory client listed and called all three · https://py.sdk.modelcontextprotocol.io/v2/migration/
Sharp edges:
- Decorators need parentheses: `@mcp.tool` without them raises TypeError ("Did you forget to call it?").
- Pass only `name` positionally. v2 inserted `title` and `description` before `instructions`, so
  `MCPServer("X", "text")` silently sets the **title**. `version` defaults to `""`.
- Type hints and Pydantic `Field(...)` build `input_schema`, and the return annotation builds `output_schema`.
  A `list[str]` return becomes `structured_content={"result": [...]}`.
- Bad arguments, an unknown tool, and `raise ToolError("msg")` (from `mcp.server.mcpserver.exceptions`) all
  return `CallToolResult(is_error=True)`, with the message in `content[0].text`.
- `ToolAnnotations` fields are snake_case (`read_only_hint`, `destructive_hint`, `idempotent_hint`,
  `open_world_hint`). The spec says clients MUST treat annotations as untrusted unless the server is trusted.
- Sync `def` handlers run on a worker thread. `MCP_*` env vars and `.env` files are NOT read.

### 2.2 Running: stdio and Streamable HTTP
```python
mcp.run()                                   # stdio (the default transport)
mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)   # serves http://127.0.0.1:8000/mcp
app = mcp.streamable_http_app()             # Starlette ASGI app to mount (no port= here)
```
verified by: introspection (`run`, `run_streamable_http_async`, `streamable_http_app`) + run (served on :8765 and called via `Client(url)`)
Sharp edges:
- `host`, `port`, `json_response` and `stateless_http` moved to `run()`; `MCPServer(port=...)` raises TypeError.
- Defaults: path `/mcp`, 4 MiB body cap (413). DNS-rebinding protection turns on automatically for localhost. A real hostname needs
  `transport_security=TransportSecuritySettings(allowed_hosts=[...])` (from `mcp.server.transport_security`);
  otherwise requests get HTTP 421.
- `stateless_http=True` affects only legacy (≤2025-11-25) clients, because 2026-07-28 has no sessions anyway.
- If you mount the app, the host lifespan must run `async with mcp.session_manager.run():`.
- `uv run mcp dev server.py` starts the server plus the Inspector and needs `npx` (from the docs; not run).

### 2.3 Client: `Client` (stdio, HTTP, list_tools, call_tool)
```python
import asyncio
from mcp import Client, StdioServerParameters

async def main() -> None:
    params = StdioServerParameters(command="python", args=["server.py"])   # or Client("http://127.0.0.1:8000/mcp")
    async with Client(params) as client:
        print(client.protocol_version)                # "2026-07-28" against a v2 server
        tools = await client.list_tools()             # ListToolsResult -> .tools[i].name/.input_schema
        result = await client.call_tool("search_docs", {"query": "mcp"})
        print(result.is_error, result.structured_content, result.content[0].text)

asyncio.run(main())
```
verified by: introspection (`Client.__init__`, `list_tools`, `call_tool`, `read_resource`, `get_prompt`) + run (stdio, HTTP, in-memory)
Sharp edges:
- `Client(x)` picks the transport by type: `str` = HTTP URL, `StdioServerParameters` = subprocess, server object = in-process, else = transport.
- Fields are snake_case (`input_schema`, `structured_content`, `is_error`, `uri_template`, `mime_type`).
  The v1 camelCase names raise AttributeError.
- Resources/prompts: `(await client.read_resource("docs://42")).contents[0].text`, `(await client.get_prompt("summarize", {"topic": "x"})).messages`.
- `mode="auto"` (the default) probes `server/discover`, then falls back to `initialize`. A run with
  `mode="legacy"` got protocol `2025-11-25`. Timeouts are float seconds.
- Headers or auth:
  `Client(streamable_http_client(url, http_client=httpx2.AsyncClient(headers={...}, timeout=httpx2.Timeout(30, read=300))))`.
  `streamable_http_client` lives in `mcp.client.streamable_http`; this was run with a bearer token.
- To bridge to Responses function tools, map `t.name`, `t.description` and `t.input_schema` to
  `{"type":"function","name","description","parameters"}`. This is writer-owned glue, not an SDK API.

### 2.4 In-memory test client (pytest)
```python
import pytest
from mcp import Client
from server import mcp

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_search() -> None:
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool("search_docs", {"query": "x", "k": 1})
        assert not result.is_error and result.structured_content == {"result": ["doc about x #0"]}
```
verified by: run (pytest 9.2.0 passed) · https://py.sdk.modelcontextprotocol.io/v2/get-started/testing/
Sharp edges:
- `pytest.mark.anyio` comes from anyio's own plugin, so pytest-asyncio is not needed.
- `create_connected_server_and_client_session` is gone. The in-memory client skips HTTP, and with it auth.
- It defaults to the 2026-07-28 era, where `ctx.elicit()` and sampling raise `NoBackChannelError`.

### 2.5 OAuth 2.1 resource server (SDK `TokenVerifier` + `AuthSettings`)
```python
from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token   # caller identity in a tool

RESOURCE = "http://127.0.0.1:8000/mcp"
class MyVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        ...  # real code: verify JWT signature/iss/aud/exp, or RFC 7662 introspection; None = reject
mcp = MCPServer("atlas-docs", token_verifier=MyVerifier(), auth=AuthSettings(
    issuer_url="https://auth.example.com", resource_server_url=RESOURCE,
    required_scopes=["docs:read"], validate_token_resource=True))
```
verified by: introspection + run · https://py.sdk.modelcontextprotocol.io/v2/run/authorization/

Run results: no token = 401 with `WWW-Authenticate: ... resource_metadata=`; wrong `resource` = 401; missing scope = 403 `insufficient_scope`; good token passes (`get_access_token()` gives `client_id`, `scopes`); `/.well-known/oauth-protected-resource/mcp` serves RFC 9728 metadata.

Sharp edges:
- `issuer_url` and `resource_server_url` are required; `token_verifier=` and `auth=` go together (one alone = ValueError).
- Leaving `validate_token_resource` unset warns (`MCPDeprecationWarning`) and behaves as False until 3.0.
  **Set it to True**: this audience check is the token-passthrough defence. Otherwise check `aud` in the verifier.
- `AccessToken(token, client_id, scopes, expires_at=None, resource=None, subject=None, claims=None)`.
- `required_scopes` applies server-wide; check per-tool scopes yourself via `get_access_token().scopes`.
- Auth is HTTP-only (stdio never checked). The SDK never issues tokens: use an IdP, or a mock verifier in lessons.

### 2.6 OpenAI Responses: remote MCP tool (hosted; OpenAI's servers call the MCP server)
```python
import os
from openai import OpenAI

client = OpenAI()
MODEL = os.environ.get("ATLAS_MODEL", "gpt-6-luna")      # gpt-6-luna lists `mcp` in supported tools
resp = client.responses.create(
    model=MODEL,
    tools=[{"type": "mcp", "server_label": "openai_docs",
            "server_description": "Search and read the public OpenAI documentation.",
            "server_url": "https://developers.openai.com/mcp",
            "allowed_tools": ["search_openai_docs"], "require_approval": "never"}],
    input="Find the Responses API streaming guide.",
)
print(resp.output_text)   # output items: mcp_list_tools, mcp_call (and mcp_approval_request)
```
verified by: introspection (`tool_param.Mcp`; output items `McpCall`, `McpListTools`, `McpApprovalRequest`) · https://developers.openai.com/api/docs/guides/tools-connectors-mcp
Sharp edges:
- Required: `type="mcp"`, `server_label`, and one of `server_url`, `connector_id` or `tunnel_id`.
- Optional: `server_description`, `allowed_tools` (list or filter), `require_approval` (`"always"`, `"never"`, or `{"never": {"tool_names": [...]}}`), `authorization` (an OAuth token string), `headers`, `defer_loading` (used with tool_search), `allowed_callers`.
- **Approval is required by default** (an `mcp_approval_request` item). Reply with `previous_response_id=resp.id` and `input=[{"type":"mcp_approval_response","approve":True,"approval_request_id":item.id}]`.
- OpenAI calls `server_url` itself, so it can't be localhost. Per the docs, private servers need `tunnel_id` (Secure MCP Tunnel); otherwise use your own `Client` loop.
- Tokens only, no per-call MCP fee (docs, as of 2026-11-06). Data sent to a third-party server follows that server's retention policy, so ZDR and residency stop there.

### 2.7 Inspector, registry, security docs (verified from docs, not executed)
**Inspector**
- A Node app, run with `npx @modelcontextprotocol/inspector [<launch cmd> | --server-url <url> --transport http]`.
- Modes: `--web` (the default), `--cli` (for CI) and `--tui`. Python docs use `uv run mcp dev server.py`.
- Node: the docs say "22.19.0 or newer"; npm 2.14.0 `engines` is stricter (`^22.23.4 || ^24.22.1 || >=26.12.1`).
- Without an OS keychain, secrets go to `~/.mcp-inspector/secrets.json` unencrypted. No-Node path: the 2.4 test client.

**Registry** (official, but "in preview": breaking changes and data resets are possible)
- `https://registry.modelcontextprotocol.io`, an unauthenticated, read-only REST API.
- Search: `GET /v0.1/servers?search=<name substring, at least 3 chars>&version=latest&limit=<1..100>`.
- Paginate with `cursor=metadata.nextCursor` (`/v0.1/servers` and `/v0/servers` both returned 200). Names are reverse-DNS (`io.github.user/server`). The registry holds metadata only and does no security scanning.

**Security best practices (2026-07-28)**
- *Confused deputy*: an MCP proxy that uses a static client ID, combined with consent cookies, lets attackers
  steal auth codes. Fix: per-client consent before the third-party flow.
- *Token passthrough* is forbidden: "MCP servers MUST NOT accept any tokens that were not explicitly issued
  for the MCP server". Defend with audience validation (RFC 8707/9068).
- The same page also covers SSRF, state-handle hijacking, local server compromise and scope minimization.
- *Tool poisoning* lives on **Local Server Security**, not that page:
  - Threats: hidden directives in tool names and descriptions; "tool shadowing"; "rug pull" (definitions change after approval).
  - Fixes: treat definitions as untrusted, review them in the Inspector, pin them, keep the server roster small.
- OpenAI's MCP guide adds that servers may hide prompt injections, and "may update tool behavior unexpectedly".

### 2.8 fastmcp (separate project, optional)
- `from fastmcp import FastMCP`. Here `@mcp.tool` works without parentheses.
- Run on 4.1.6: `Client(m).call_tool(...)` returned a `CallToolResult` with `.data == 3`.
- Its API differs from the SDK's `MCPServer`, so never mix the two in one lesson.

## 3. IDS / VERSIONS / PRICES
**Spec revision `2026-07-28`** is the latest; the previous one was `2025-11-25`. The changelog
(checked 2026-11-06, https://modelcontextprotocol.io/specification/2026-07-28/changelog) lists:
1. **Stateless:** the `initialize` handshake is gone. Every request carries `_meta` with `io.modelcontextprotocol/protocolVersion` and `clientCapabilities`.
2. **No sessions:** `Mcp-Session-Id` is gone. Servers mint handles and pass them as ordinary tool arguments.
3. **Discovery/subscriptions:** new `server/discover` (servers MUST implement); `subscriptions/listen` replaces the HTTP GET stream and `resources/subscribe`.
4. **Removed:** `ping`, `logging/setLevel`, and SSE resumability (`Last-Event-ID`).
5. **MRTR:** `InputRequiredResult` replaces server→client requests (sampling, elicitation, roots). Every result carries a `resultType`.
6. **Tasks** moved out to an extension (`io.modelcontextprotocol/tasks`).
7. **Minor:** `Mcp-Method`/`Mcp-Name` headers required on POST; list results carry `ttlMs`/`cacheScope`; resource-not-found is `-32602`; `traceparent` in `_meta`; any JSON Schema 2020-12 keyword allowed.

**Transports:** stdio and Streamable HTTP. The SDK still ships SSE (`run(transport="sse")`), but SSE is deprecated.

**Packages** (PyPI, as of 2026-11-06; https://pypi.org/pypi/mcp/json):
- `mcp` 2.3.0 (2026-10-02). 2.0.0 shipped 2026-07-28; v1 is still patched (1.30.0 on 2026-09-07).
- `fastmcp` 4.1.6 (2026-11-03; PrefectHQ; active; 4.2.0a3 pre-release). It depends on `mcp-types`, not on `mcp`.
- `@modelcontextprotocol/inspector` 2.14.0 (npm).

**Prices:** MCP is free. The OpenAI MCP tool bills tokens only (2.6).

**MCP Apps** is a **Stable** extension for interactive UI inline in hosts (https://modelcontextprotocol.io/docs/extensions/overview).

## 4. DON'T USE
| Don't | Use instead |
|---|---|
| `from mcp.server.fastmcp import FastMCP` (ModuleNotFoundError in 2.x) | `from mcp.server import MCPServer` |
| Low-level `Server` + `@server.list_tools()` / `@server.call_tool()` (removed) | `MCPServer` decorators (low-level now takes `on_*` constructor params; advanced only) |
| `MCPServer("X", host=..., port=..., stateless_http=...)` | `mcp.run(transport="streamable-http", host=..., port=...)` |
| `streamablehttp_client(...)` and its 3-tuple (removed) | `Client(url)`, or `streamable_http_client(url, http_client=httpx2.AsyncClient(...))` |
| `ClientSession` + `stdio_client` + `initialize()` boilerplate | `async with Client(StdioServerParameters(...))` |
| `create_connected_server_and_client_session` | in-memory `Client(server)` |
| `McpError`; camelCase fields (`inputSchema`, `isError`) | `MCPError`; snake_case fields |
| `httpx.AsyncClient` passed into the SDK | `httpx2.AsyncClient` |
| HTTP+SSE (`transport="sse"`, `sse_client`); the WebSocket transport (removed) | Streamable HTTP |
| Roots, Sampling, Logging (deprecated in spec 2026-07-28 by SEP-2577; the SDK warns with `MCPDeprecationWarning`) | Tool params or config; call the LLM API directly; stderr or OpenTelemetry |
| `ctx.info()` for observability (dropped on 2026-era connections unless the client sets `log_level=`) | stderr or OpenTelemetry |
| Dynamic Client Registration (deprecated) | Client ID Metadata Documents |
| `send_ping()`, `resources/subscribe` (removed in 2026-07-28) | `client.listen(...)` |
| Teaching `initialize` / `Mcp-Session-Id` as how MCP works | `server/discover` + stateless requests (`mode="legacy"` only for old servers) |
| OpenAI `connector_id` (deprecated for models released after 2026-09-01) | `server_url`, or `tunnel_id` |

## 5. ⚠ VERIFY RESOLUTIONS
- D039 | transports: stdio, Streamable HTTP | CONFIRMED. HTTP+SSE is Deprecated, and the SDK removed WebSocket.
- D039 | "stateless 2026 spec" | CONFIRMED. 2026-07-28 drops `initialize` and `Mcp-Session-Id` and adds `server/discover` (section 3).
- D039 | Roots/Sampling/HTTP+SSE deprecations | CORRECTED. **Logging** and Dynamic Client Registration are also deprecated, and `ping`, `logging/setLevel` and `resources/subscribe` are *removed*, not deprecated.
- D039 | remote MCP via Responses + your own client | CONFIRMED (2.6, 2.3), with a CORRECTION: the Responses `mcp` tool can't reach localhost. The build's "local one" must use your own `Client` bridged to function tools, or `tunnel_id` (prose only, ⚠ verify).
- D040 | `MCPServer` (SDK v2) | CONFIRMED: `from mcp.server import MCPServer`, mcp 2.3.0.
- D040 | Python test client; Inspector needs Node | CONFIRMED. `Client(mcp)` works in-memory, and the Inspector needs Node ≥22.19. SYLLABUS's "testing with the Inspector" should read "Python test client first, Inspector optional".
- D074 | confused deputy, token passthrough | CONFIRMED (Security Best Practices).
- D074 | tool poisoning | CORRECTED source: cite **Local Server Security**, not Security Best Practices, plus the OpenAI MCP guide's warnings.
- D074 | OAuth 2.1 resource server via a library, validating tokens and scopes | CONFIRMED (2.5): the SDK's `TokenVerifier` + `AuthSettings(validate_token_resource=True)`. Issuing tokens needs an external IdP, so mock the verifier.
- D080 | MCP Apps (overview) | CONFIRMED as a Stable extension (`modelcontextprotocol/ext-apps`). No API shape was verified, so keep it to an overview.
- B_currency | mcp row | CONFIRMED: `MCPServer`, `on_*`, `Client(url)`, `streamablehttp_client` removed, httpx2, snake_case, SEP-2577. Nuance: the docs say Python 3.11+, PyPI says `>=3.10`.
- B_currency | fastmcp row | CONFIRMED: 4.1.6, PrefectHQ, active.

## 6. VERIFIED LINKS
All returned HTTP 200 on 2026-11-06. For raw markdown, append `.md` to a modelcontextprotocol.io page.
- https://modelcontextprotocol.io/specification/2026-07-28/changelog: what changed in 2026-07-28
- https://modelcontextprotocol.io/specification/2026-07-28/deprecated: deprecated-features registry with migration paths
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http: Streamable HTTP transport spec
- https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization: authorization spec (MCP server as OAuth 2.1 resource server)
- https://modelcontextprotocol.io/specification/2026-07-28/server/tools: tools spec (annotations untrusted, human in the loop)
- https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices: confused deputy, token passthrough, SSRF
- https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/local-server-security: tool poisoning, shadowing, rug pulls
- https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector: MCP Inspector (npx; web, CLI and TUI; Node requirement)
- https://modelcontextprotocol.io/registry/about: official MCP Registry overview (preview, namespaces)
- https://modelcontextprotocol.io/registry/registry-aggregators: registry REST API (`/v0.1/servers`, pagination)
- https://registry.modelcontextprotocol.io/docs: registry OpenAPI reference (`search`, `version`, `limit`)
- https://modelcontextprotocol.io/docs/extensions/overview: extensions, including MCP Apps (Stable)
- https://py.sdk.modelcontextprotocol.io/v2/: Python SDK v2 docs home (install, first server, `mcp dev`)
- https://py.sdk.modelcontextprotocol.io/v2/migration/: v1→v2 migration guide
- https://py.sdk.modelcontextprotocol.io/v2/get-started/testing/: in-memory `Client(mcp)` testing
- https://py.sdk.modelcontextprotocol.io/v2/client/transports/: client transports (URL, stdio, in-memory, httpx2)
- https://py.sdk.modelcontextprotocol.io/v2/protocol-versions/: `mode="auto"` vs `"legacy"`
- https://py.sdk.modelcontextprotocol.io/v2/run/authorization/: SDK resource-server auth
- https://developers.openai.com/api/docs/guides/tools-connectors-mcp: OpenAI Responses remote MCP tool
- https://github.com/PrefectHQ/fastmcp: standalone FastMCP project (separate from the SDK)
