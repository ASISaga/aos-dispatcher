# aos-dispatcher Repository Specification

**Version**: 1.0.0
**Status**: Active
**Last Updated**: 2026-03-07

## Overview

`aos-dispatcher` is the **central dispatcher** for the Agent Operating System (AOS) — the component that receives all inbound requests and dispatches them to the AOS kernel, analogous to the dispatcher in a traditional operating system.

The repository is split into **two parts**:

1. **`src/aos_dispatcher/`** — Pure Python dispatcher library. Framework-agnostic; no dependency on `azure.functions`. Contains all business logic: orchestration processing, in-memory stores, app registration, knowledge base, risk registry, audit trail, covenants, analytics, MCP proxy, agent management, and network discovery. This package is retained in this repository and published as the `aos-dispatcher` Python library.

2. **`azure_functions/`** — Thin Azure Functions wrapper that imports `aos_dispatcher` and exposes all operations as Azure HTTP endpoints and Service Bus triggers. This directory is intended to be **manually moved to the main `agent-operating-system` repository** where it will be deployed as an Azure Function App.

All multi-agent orchestration is managed internally by the **Foundry Agent Service**. Agents inheriting from `PurposeDrivenAgent` run as Azure Functions. Foundry is an implementation detail — clients interact only with the standard orchestration endpoints via the `aos-client-sdk`.

## Scope

- Repository role in the AOS ecosystem
- Technology stack and coding patterns
- API surface: HTTP endpoints and Service Bus triggers
- Testing and validation workflows
- Key design principles for agents and contributors

## Repository Role

| Concern | Owner |
|---------|-------|
| HTTP and Service Bus dispatch layer | **aos-dispatcher** |
| MCP server deployment and tool routing | **aos-mcp-servers** (ASISaga/mcp) |
| Agent catalog (CEO, CFO, CMO, COO agents) | **aos-realm-of-agents** (ASISaga/realm-of-agents) |
| Orchestration engine, messaging, storage, auth, MCP, monitoring | `aos-kernel` |
| Client SDK and app framework | `aos-client-sdk` |
| Infrastructure provisioning and deployment | `aos-infrastructure` |

`aos-dispatcher` **owns the API surface**. It does not implement agent intelligence or kernel logic — it routes requests to the kernel and returns structured responses.

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.10+ |
| Dispatcher library | `src/aos_dispatcher/` — no Azure dependencies |
| Azure Functions wrapper | `azure_functions/` — `azure-functions >= 1.21.0` |
| Messaging (Azure Functions only) | `azure-servicebus >= 7.12.0` |
| Kernel integration | `aos-kernel[azure] >= 3.0.0` |
| Agent orchestration | `agent-framework >= 1.0.0rc1`, `agent-framework-orchestrations`, `agent-framework-azurefunctions` (wrapper only) |
| Intelligence (optional) | `aos-intelligence[foundry] >= 1.0.0` |
| Tests | `pytest >= 8.0.0` + `pytest-asyncio >= 0.24.0` |
| Linter | `pylint >= 3.0.0` |
| Build / deploy | `azure.yaml` (Azure Developer CLI), `azd deploy aos-dispatcher` |

## Directory Structure

```
aos-dispatcher/
├── src/
│   └── aos_dispatcher/         # Pure Python dispatcher library
│       ├── __init__.py         # Public API exports
│       └── dispatcher.py       # All business logic — no azure.functions dep
├── azure_functions/             # Azure Functions wrapper (to be moved to agent-operating-system)
│   ├── function_app.py         # Thin Azure Functions HTTP/Service Bus handlers
│   ├── host.json               # Azure Functions host configuration
│   └── pyproject.toml          # Azure Functions project config (depends on aos-dispatcher)
├── tests/
│   ├── __init__.py
│   ├── test_dispatcher.py      # pytest unit tests for the pure library
│   └── test_function_app.py    # Legacy tests (kept for backward compat, same coverage)
├── docs/
│   ├── architecture.md         # System architecture and component diagram
│   ├── api-reference.md        # HTTP endpoint and configuration reference
│   └── contributing.md         # Contribution guide
├── .github/
│   ├── spec/                   # Repository and intelligence system specifications ← here
│   ├── workflows/
│   │   ├── ci.yml              # CI: pytest (Python 3.10/3.11/3.12) + pylint
│   │   └── deploy.yml          # Deploy: azd deploy aos-dispatcher
│   ├── skills/azure-functions/ # Azure Functions development skill
│   ├── prompts/azure-expert.md # Azure & cloud expert agent prompt
│   └── instructions/azure-functions.instructions.md
├── pyproject.toml              # Library build config and pytest settings (no azure-functions dep)
├── azure.yaml                  # Azure Developer CLI — points to azure_functions/
└── README.md
```

## API Surface

### HTTP Endpoints

| Group | Method | Route | Description |
|-------|--------|-------|-------------|
| **Orchestrations** | POST | `/api/orchestrations` | Submit an orchestration request |
| | GET | `/api/orchestrations/{id}` | Poll orchestration status |
| | GET | `/api/orchestrations/{id}/result` | Retrieve completed result |
| | POST | `/api/orchestrations/{id}/cancel` | Cancel a running orchestration |
| **Knowledge Base** | POST | `/api/knowledge/documents` | Create a document |
| | GET | `/api/knowledge/documents` | Search documents |
| | GET | `/api/knowledge/documents/{id}` | Get document by ID |
| | POST | `/api/knowledge/documents/{id}` | Update document |
| | DELETE | `/api/knowledge/documents/{id}` | Delete document |
| **Risk Registry** | POST | `/api/risks` | Register a risk |
| | GET | `/api/risks` | List risks |
| | POST | `/api/risks/{id}/assess` | Assess a risk |
| | POST | `/api/risks/{id}/status` | Update risk status |
| | POST | `/api/risks/{id}/mitigate` | Add mitigation plan |
| **Audit Trail** | POST | `/api/audit/decisions` | Log a decision |
| | GET | `/api/audit/decisions` | Get decision history |
| | GET | `/api/audit/trail` | Get audit trail |
| **Covenants** | POST | `/api/covenants` | Create a covenant |
| | GET | `/api/covenants` | List covenants |
| | GET | `/api/covenants/{id}/validate` | Validate a covenant |
| | POST | `/api/covenants/{id}/sign` | Sign a covenant |
| **Analytics** | POST | `/api/metrics` | Record a metric |
| | GET | `/api/metrics` | Get metric series |
| | POST | `/api/kpis` | Create a KPI |
| | GET | `/api/kpis/dashboard` | Get KPI dashboard |
| **MCP** | GET | `/api/mcp/servers` | List MCP servers (proxied to aos-mcp-servers) |
| | POST | `/api/mcp/servers/{s}/tools/{t}` | Call an MCP tool (proxied to aos-mcp-servers) |
| | GET | `/api/mcp/servers/{s}/status` | Get MCP server status (proxied to aos-mcp-servers) |
| **Agents** | GET | `/api/agents` | List agents (proxied to aos-realm-of-agents) |
| | GET | `/api/agents/{id}` | Get agent descriptor (proxied to aos-realm-of-agents) |
| | POST | `/api/agents/register` | Register a PurposeDrivenAgent with Foundry |
| | POST | `/api/agents/{id}/ask` | Ask an agent |
| | POST | `/api/agents/{id}/send` | Send to an agent |
| | POST | `/api/agents/{id}/message` | Send message via Foundry bridge |
| **Network** | POST | `/api/network/discover` | Discover peers |
| | POST | `/api/network/{id}/join` | Join a network |
| | GET | `/api/network` | List networks |
| **App Registration** | POST | `/api/apps/register` | Register a client application |
| | GET | `/api/apps/{app_name}` | Get app registration status |
| | DELETE | `/api/apps/{app_name}` | Deregister a client application |
| **Health** | GET | `/api/health` | Health check |

### Service Bus Triggers

| Queue | Function | Description |
|-------|----------|-------------|
| `aos-orchestration-requests` | `service_bus_orchestration_request` | Process incoming orchestration requests from client apps |

## Core Patterns

### Two-Part Architecture

The repository is split into a pure Python library and an Azure Functions wrapper:

```
                ┌─────────────────────────────────┐
                │  azure_functions/function_app.py │  ← Azure Functions wrapper
                │  (to be moved to agent-OS repo) │
                │  @app.route(...) handlers        │
                │  _make_response() / _require_json│
                └──────────────┬──────────────────┘
                               │ imports
                               ▼
                ┌─────────────────────────────────┐
                │  src/aos_dispatcher/dispatcher.py│  ← Pure Python library
                │  (stays in this repo)           │
                │  Returns (body, status_code)     │
                │  No azure.functions dependency  │
                └─────────────────────────────────┘
```

### Library Response Convention

All `dispatcher.py` functions return a `(body, status_code)` tuple:
- `body` is a `dict` (JSON-serialisable), `bytes` (proxy pass-through), or `None` (204 No Content)
- The Azure Functions wrapper converts this to `func.HttpResponse` via `_make_response()`

### Orchestration Request Processing

The shared `process_orchestration_request` function is called by both the HTTP endpoint and the Service Bus trigger. It registers agents with the Foundry Agent Service and stores orchestration records in memory.

```python
def process_orchestration_request(
    body: Dict[str, Any],
    source_app: str | None = None,
) -> tuple[Dict[str, Any], int]:
    agent_ids = body.get("agent_ids", [])
    if not agent_ids:
        return {"error": "agent_ids must be a non-empty list"}, 400
    orch_id = body.get("orchestration_id") or str(uuid.uuid4())
    # ... register with Foundry, store record, return ({...}, 202)
```

### App Registration

Client apps register via `POST /api/apps/register` to receive Service Bus connection details. The registration provisions queue/topic/subscription names and returns a connection string.

### Error Response Convention

All error responses return `({"error": "<message>"}, status_code)`. The Azure Functions wrapper serialises these to `application/json` with the appropriate HTTP status code.

## Testing Workflow

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Lint
pylint src/ --fail-under=5.0
```

**CI**: GitHub Actions (`ci.yml`) runs `pytest` across Python 3.10, 3.11, and 3.12, and `pylint` on every push/PR to `main` and `develop`.

→ **CI workflow**: `.github/workflows/ci.yml`

## Deployment

```bash
# Deploy via the aos-infrastructure orchestrator (recommended), or directly:
azd deploy aos-dispatcher
```

→ **Deploy workflow**: `.github/workflows/deploy.yml`
→ **Azure config**: `azure.yaml`

## Related Repositories

| Repository | Role |
|-----------|------|
| [aos-client-sdk](https://github.com/ASISaga/aos-client-sdk) | Client SDK — used by client apps to talk to this dispatcher |
| [aos-kernel](https://github.com/ASISaga/aos-kernel) | AOS kernel — orchestration engine, messaging, storage, monitoring |
| [mcp](https://github.com/ASISaga/mcp) | **aos-mcp-servers** function app — config-driven MCP server deployment & tool routing |
| [realm-of-agents](https://github.com/ASISaga/realm-of-agents) | **aos-realm-of-agents** function app — agent catalog (CEO, CFO, CMO, COO agents) |
| [aos-intelligence](https://github.com/ASISaga/aos-intelligence) | ML / intelligence layer |
| [business-infinity](https://github.com/ASISaga/business-infinity) | Example client application |
| [aos-infrastructure](https://github.com/ASISaga/aos-infrastructure) | Infrastructure deployment orchestrator |

## Key Design Principles

1. **Dispatcher pattern** — Receives all inbound requests and routes them; contains no business or agent logic
2. **Foundry-managed orchestrations** — All agent lifecycle is managed by the Foundry Agent Service; clients never interact with agents directly
3. **Shared HTTP/Service Bus logic** — `_process_orchestration_request` is called from both the HTTP handler and the Service Bus trigger to avoid duplication
4. **Environment-based configuration** — All secrets and connection strings come from Azure App Settings; never hardcoded
5. **Async handlers** — All Azure Functions handlers are `async def` for throughput
6. **Structured JSON responses** — All endpoints return `application/json`; errors follow `{"error": "<message>"}` convention

## References

→ **Architecture**: `docs/architecture.md`
→ **API reference**: `docs/api-reference.md`
→ **Contributing**: `docs/contributing.md`
→ **Azure Functions skill**: `.github/skills/azure-functions/SKILL.md`
→ **Azure expert prompt**: `.github/prompts/azure-expert.md`
→ **Azure Functions instructions**: `.github/instructions/azure-functions.instructions.md`
→ **CI workflow**: `.github/workflows/ci.yml`
→ **Deploy workflow**: `.github/workflows/deploy.yml`
