# aos-dispatcher Architecture

## Overview

The AOS Dispatcher is the **central HTTP/Service Bus dispatcher** for the Agent Operating System.
Client applications submit orchestration requests and retrieve results through the HTTP endpoints
exposed by this dispatcher.

The `aos-dispatcher` repository is structured in **two parts**:

| Part | Location | Purpose |
|------|----------|---------|
| **Python library** | `src/aos_dispatcher/` | Pure Python dispatcher logic — no `azure.functions` dependency. Import from any hosting framework. |
| **Azure Functions wrapper** | `azure_functions/` | Thin bindings that expose the library as Azure HTTP endpoints and Service Bus triggers. Intended to be deployed as part of the `agent-operating-system` repository. |

The AOS platform is deployed as **3 separate Azure Functions apps**:

| Function App | Repository | Responsibility |
|---|---|---|
| **aos-dispatcher** | [ASISaga/aos-dispatcher](https://github.com/ASISaga/aos-dispatcher) | Central dispatcher — orchestrations, app registration, knowledge base, risk registry, audit, covenants, analytics, health |
| **aos-mcp-servers** | [ASISaga/mcp](https://github.com/ASISaga/mcp) | Config-driven MCP server deployment and tool routing |
| **aos-realm-of-agents** | [ASISaga/realm-of-agents](https://github.com/ASISaga/realm-of-agents) | Agent catalog & registry (CEO, CFO, CMO, COO agents) |

## Component Architecture

```
┌─────────────────────────────────────┐
│   Client Applications               │
│   (BusinessInfinity, etc.)          │
│   pip install aos-client-sdk        │
└─────────────────────────────────────┘
              │
         HTTPS (aos-client-sdk)
              │
              ▼
┌─────────────────────────────────────┐
│   aos-dispatcher  (Function App 1)  │
│   POST /api/orchestrations          │
│   GET  /api/orchestrations/{id}     │
│   GET  /api/orchestrations/{id}/    │
│         result                      │
│   POST /api/orchestrations/{id}/    │
│         cancel                      │
│   /api/knowledge/*, /api/risks/*    │
│   /api/audit/*, /api/covenants/*    │
│   /api/metrics/*, /api/kpis/*       │
│   /api/apps/*, /api/health          │
│   /api/mcp/* → proxied ─────────────┼──→ aos-mcp-servers (Function App 2)
│   /api/agents (GET) → proxied ──────┼──→ aos-realm-of-agents (Function App 3)
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│   aos-kernel                        │
│   Orchestration engine, Messaging,  │
│   Storage, Auth, MCP, Monitoring    │
└─────────────────────────────────────┘

┌──────────────────────────────────┐   ┌──────────────────────────────────┐
│  aos-mcp-servers (Function App 2)│   │ aos-realm-of-agents (Function    │
│  GET  /api/mcp/servers           │   │ App 3)                           │
│  GET  /api/mcp/servers/{id}      │   │ GET /api/realm/agents            │
│  POST /api/mcp/servers/{id}/     │   │ GET /api/realm/agents/{id}       │
│        tools/{tool}              │   │ GET /api/realm/config            │
│  GET  /api/health                │   │ GET /api/health                  │
└──────────────────────────────────┘   └──────────────────────────────────┘
```

## Key Principle

> AOS provides agent orchestrations as an infrastructure service.
> Client apps contain only business logic — AOS handles the rest.

## Proxy Configuration

`aos-dispatcher` proxies MCP and agent-catalog requests to the other two function apps.
Set the following App Settings in your Azure deployment:

| Setting | Description |
|---------|-------------|
| `MCP_SERVERS_BASE_URL` | Base URL of the `aos-mcp-servers` function app (e.g. `https://aos-mcp-servers.azurewebsites.net`) |
| `REALM_OF_AGENTS_BASE_URL` | Base URL of the `aos-realm-of-agents` function app (e.g. `https://aos-realm-of-agents.azurewebsites.net`) |

When these variables are not set the dispatcher returns stub/in-memory responses (useful for local development).

## HTTP Endpoints

### Orchestration API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/orchestrations` | Submit an orchestration request |
| GET | `/api/orchestrations/{id}` | Poll orchestration status |
| GET | `/api/orchestrations/{id}/result` | Retrieve completed result |
| POST | `/api/orchestrations/{id}/cancel` | Cancel a running orchestration |
| GET | `/api/health` | Health check |

### Orchestration Request Body

```json
{
    "orchestration_id": "optional-client-id",
    "agent_ids": ["ceo", "cfo", "cmo"],
    "workflow": "collaborative",
    "task": {"type": "strategic_review", "data": {"quarter": "Q1-2026"}},
    "config": {},
    "callback_url": null
}
```

## Configuration

| Setting | Description |
|---------|-------------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage connection |
| `AZURE_SERVICEBUS_CONNECTION_STRING` | Service Bus connection |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights telemetry |
| `APP_ENVIRONMENT` | Environment name (dev/staging/prod) |
| `MCP_SERVERS_BASE_URL` | Base URL of the aos-mcp-servers function app |
| `REALM_OF_AGENTS_BASE_URL` | Base URL of the aos-realm-of-agents function app |

## Related Repositories

- [aos-client-sdk](https://github.com/ASISaga/aos-client-sdk) — Client SDK
- [aos-kernel](https://github.com/ASISaga/aos-kernel) — OS kernel
- [mcp](https://github.com/ASISaga/mcp) — aos-mcp-servers function app
- [realm-of-agents](https://github.com/ASISaga/realm-of-agents) — aos-realm-of-agents function app
- [aos-intelligence](https://github.com/ASISaga/aos-intelligence) — ML / intelligence layer
- [business-infinity](https://github.com/ASISaga/business-infinity) — Example client app
- [aos-infrastructure](https://github.com/ASISaga/aos-infrastructure) — Deployment
