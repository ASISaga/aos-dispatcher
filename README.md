# aos-dispatcher

**Central Dispatcher** for the Agent Operating System — the component that receives all inbound requests and dispatches them to the AOS kernel, analogous to the dispatcher in a traditional operating system.

## Repository Structure

This repository is split into **two parts**:

| Part | Location | Purpose |
|------|----------|---------|
| **Python library** | `src/aos_dispatcher/` | Pure Python dispatcher core — no `azure.functions` dependency. Import from any hosting framework. |
| **Azure Functions wrapper** | `azure_functions/` | Thin bindings that expose the library as Azure HTTP/Service Bus endpoints. Intended to be moved to the `agent-operating-system` repository for deployment. |

## Library Usage

```python
from aos_dispatcher import dispatcher

# Process an orchestration request (returns a (body_dict, status_code) tuple)
body, status = dispatcher.process_orchestration_request({
    "agent_ids": ["ceo", "cfo", "cmo"],
    "workflow": "collaborative",
    "task": {"type": "strategic_review"},
})
```

## Client App Usage (via aos-client-sdk)

```python
from aos_client import AOSClient

async with AOSClient(endpoint="https://my-aos.azurewebsites.net") as client:
    status = await client.start_orchestration(
        agent_ids=["ceo", "cfo", "cmo"],
        purpose="strategic_review",
        context={"quarter": "Q1-2026"},
    )
    print(status.orchestration_id)
```

## Overview

The dispatcher provides:

- **Orchestration Submission** — `POST /api/orchestrations` to start agent orchestrations
- **Status Monitoring** — `GET /api/orchestrations/{id}` to poll progress
- **Result Retrieval** — `GET /api/orchestrations/{id}/result`
- **Cancellation** — `POST /api/orchestrations/{id}/cancel`
- **Health Check** — `GET /api/health`
- **Knowledge Base, Risk Registry, Audit, Covenants, Analytics** — enterprise service APIs
- **MCP & Agent Catalog** — proxied to `aos-mcp-servers` and `aos-realm-of-agents`

## Prerequisites

- Python 3.10+
- Azure Functions Core Tools v4 (only for the `azure_functions/` wrapper)
- Azure subscription with Service Bus namespace (only for deployment)

## Development

```bash
# Install library dev dependencies
pip install -e ".[dev]"

# Run tests (pure library — no azure.functions required)
pytest tests/ -v

# Lint
pylint src/
```

## Deployment

The `azure_functions/` directory is deployed as part of the `agent-operating-system` Azure Functions app.  For standalone deployment:

```bash
azd deploy aos-dispatcher
```

## Dependencies

**Library (`src/aos_dispatcher/`):**
- `aos-kernel[azure]>=3.0.0`
- `agent-framework>=1.0.0rc1`
- `agent-framework-orchestrations>=1.0.0b260219`

**Azure Functions wrapper (`azure_functions/`):**
- All of the above, plus `azure-functions>=1.21.0`, `azure-servicebus>=7.12.0`, `agent-framework-azurefunctions>=1.0.0b260219`

## Related Repositories

- [aos-client-sdk](https://github.com/ASISaga/aos-client-sdk) — Client SDK
- [aos-realm-of-agents](https://github.com/ASISaga/aos-realm-of-agents) — Agent catalog
- [aos-kernel](https://github.com/ASISaga/aos-kernel) — OS kernel
- [aos-intelligence](https://github.com/ASISaga/aos-intelligence) — ML / intelligence layer
- [business-infinity](https://github.com/ASISaga/business-infinity) — Example client app
- [aos-infrastructure](https://github.com/ASISaga/aos-infrastructure) — Infrastructure deployment

## License

Apache License 2.0 — see [LICENSE](LICENSE)

