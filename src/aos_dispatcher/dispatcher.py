"""AOS Dispatcher — pure Python business logic for the Agent Operating System.

Framework-agnostic dispatcher core with no dependency on ``azure.functions``.
Contains all in-memory stores, processing logic, and HTTP proxy utilities.

Designed to be imported by the Azure Functions wrapper (``azure_functions/``)
or any other hosting framework (FastAPI, gRPC, etc.).

All functions return a ``DispatchResponse`` tuple ``(body, status_code)`` where:
    - ``body`` is a ``dict`` (JSON-serialisable), ``bytes`` (proxy pass-through),
      or ``None`` (no body, e.g. 204 No Content).
    - ``status_code`` is an integer HTTP status code.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── Type alias ────────────────────────────────────────────────────────────────
# (body, status_code) — body is dict | bytes | None
DispatchResponse = tuple

# ── Configuration ─────────────────────────────────────────────────────────────
# Set these in Azure App Settings (or environment variables) to enable proxying
# to the dedicated downstream function apps.  When unset the endpoints fall back
# to in-memory stubs (useful for local development and unit tests).
_MCP_SERVERS_BASE_URL: str = os.environ.get("MCP_SERVERS_BASE_URL", "")
_REALM_OF_AGENTS_BASE_URL: str = os.environ.get("REALM_OF_AGENTS_BASE_URL", "")

# ── In-Memory Stores ──────────────────────────────────────────────────────────
# Development / prototype only.  In production replace with Azure Table Storage
# or Cosmos DB.

_orchestrations: Dict[str, Dict[str, Any]] = {}
_registered_apps: Dict[str, Dict[str, Any]] = {}
_documents: Dict[str, Dict[str, Any]] = {}
_risks: Dict[str, Dict[str, Any]] = {}
_decisions: list = []
_audit_entries: list = []
_covenants: Dict[str, Dict[str, Any]] = {}
_metrics_store: list = []
_kpis: Dict[str, Dict[str, Any]] = {}
_networks: Dict[str, Dict[str, Any]] = {}
_network_memberships: Dict[str, Dict[str, Any]] = {}
_foundry_agents: Dict[str, Dict[str, Any]] = {}
_foundry_orchestrations: Dict[str, Dict[str, Any]] = {}


# ── Orchestrations ────────────────────────────────────────────────────────────


def process_orchestration_request(
    body: Dict[str, Any],
    source_app: str | None = None,
) -> DispatchResponse:
    """Process an orchestration request from HTTP or Service Bus.

    All orchestrations are managed internally by the Foundry Agent Service.
    Agents are registered in the Foundry project and connected via
    conversation threads.

    Args:
        body: Parsed request body.
        source_app: Name of the source client app (for Service Bus requests).

    Returns:
        ``(status_dict, 202)`` on success or ``(error_dict, 400)`` on failure.
    """
    agent_ids = body.get("agent_ids", [])
    if not agent_ids:
        return {"error": "agent_ids must be a non-empty list"}, 400

    orch_id = body.get("orchestration_id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    purpose = body.get("purpose", {})
    purpose_text = purpose.get("purpose", "") if isinstance(purpose, dict) else str(purpose)

    # Register agents with Foundry Agent Service
    for aid in agent_ids:
        if aid not in _foundry_agents:
            _foundry_agents[aid] = {
                "agent_id": aid,
                "model": "gpt-4o",
                "name": aid,
                "instructions": "",
                "tools": [],
                "created_at": now,
                "managed_by": "foundry_agent_service",
            }

    record: Dict[str, Any] = {
        "orchestration_id": orch_id,
        "status": "pending",
        "agent_ids": agent_ids,
        "workflow": body.get("workflow", "collaborative"),
        "purpose": purpose_text,
        "context": body.get("context", {}),
        "config": body.get("config", {}),
        "callback_url": body.get("callback_url"),
        "source_app": source_app,
        "progress": 0.0,
        "created_at": now,
        "updated_at": now,
        "error": None,
        "results": {},
        "summary": None,
        "managed_by": "foundry_agent_service",
    }
    _orchestrations[orch_id] = record

    logger.info(
        "Orchestration %s submitted via Foundry Agent Service — agents=%s workflow=%s source=%s",
        orch_id,
        agent_ids,
        record["workflow"],
        source_app or "http",
    )

    return {
        "orchestration_id": orch_id,
        "status": "pending",
        "agent_ids": agent_ids,
        "purpose": purpose_text,
        "progress": 0.0,
        "created_at": now,
        "updated_at": now,
        "error": None,
    }, 202


def get_orchestration_status(orch_id: str) -> DispatchResponse:
    """Poll the status of a submitted orchestration."""
    record = _orchestrations.get(orch_id)
    if record is None:
        return {"error": f"Orchestration '{orch_id}' not found"}, 404

    return {
        "orchestration_id": record["orchestration_id"],
        "status": record["status"],
        "agent_ids": record["agent_ids"],
        "progress": record["progress"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "error": record["error"],
    }, 200


def get_orchestration_result(orch_id: str) -> DispatchResponse:
    """Retrieve the final result of a completed orchestration."""
    record = _orchestrations.get(orch_id)
    if record is None:
        return {"error": f"Orchestration '{orch_id}' not found"}, 404

    if record["status"] not in ("completed", "failed"):
        return {"error": "Orchestration has not completed yet", "status": record["status"]}, 409

    return {
        "orchestration_id": record["orchestration_id"],
        "status": record["status"],
        "agent_ids": record["agent_ids"],
        "results": record["results"],
        "summary": record["summary"],
        "created_at": record["created_at"],
        "completed_at": record.get("completed_at"),
        "duration_seconds": record.get("duration_seconds"),
    }, 200


def cancel_orchestration(orch_id: str) -> DispatchResponse:
    """Cancel a running orchestration."""
    record = _orchestrations.get(orch_id)
    if record is None:
        return {"error": f"Orchestration '{orch_id}' not found"}, 404

    if record["status"] in ("completed", "failed", "cancelled"):
        return {"error": f"Cannot cancel orchestration in '{record['status']}' state"}, 409

    record["status"] = "cancelled"
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Orchestration %s cancelled", orch_id)

    return {
        "orchestration_id": record["orchestration_id"],
        "status": "cancelled",
        "agent_ids": record["agent_ids"],
        "progress": record["progress"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "error": None,
    }, 200


# ── App Registration ──────────────────────────────────────────────────────────


def register_app(body: Dict[str, Any]) -> DispatchResponse:
    """Register a client application with AOS.

    Provisions Service Bus queues, topics, and subscriptions for async
    communication.  Returns connection details to the client.
    """
    app_name = body.get("app_name")
    if not app_name:
        return {"error": "app_name is required"}, 400

    subscription_name = app_name
    registration = {
        "app_name": app_name,
        "app_id": body.get("app_id"),
        "workflows": body.get("workflows", []),
        "request_queue": "aos-orchestration-requests",
        "result_topic": "aos-orchestration-results",
        "result_subscription": subscription_name,
        "status": "provisioned",
        "provisioned_resources": {
            "service_bus_queue": "aos-orchestration-requests",
            "service_bus_topic": "aos-orchestration-results",
            "service_bus_subscription": subscription_name,
        },
        "service_bus_connection_string": os.environ.get("SERVICE_BUS_CONNECTION"),
    }

    _registered_apps[app_name] = registration

    logger.info(
        "Registered app '%s' — workflows=%s subscription=%s",
        app_name,
        registration["workflows"],
        subscription_name,
    )

    # TODO: Actually provision Service Bus resources via Azure SDK
    # - Create subscription on aos-orchestration-results topic filtered by app_name
    # - Set up managed identity role assignments

    return registration, 201


def get_app_registration(app_name: str) -> DispatchResponse:
    """Get the registration status of a client application."""
    registration = _registered_apps.get(app_name)
    if registration is None:
        return {"error": f"App '{app_name}' not registered"}, 404
    return registration, 200


def deregister_app(app_name: str) -> DispatchResponse:
    """Remove a client application registration."""
    if app_name not in _registered_apps:
        return {"error": f"App '{app_name}' not registered"}, 404

    del _registered_apps[app_name]
    logger.info("Deregistered app '%s'", app_name)

    # TODO: Clean up provisioned Service Bus resources

    return None, 204


# ── Health ────────────────────────────────────────────────────────────────────


def health() -> DispatchResponse:
    """Return the health status of the dispatcher."""
    return {
        "app": "aos-dispatcher",
        "status": "healthy",
        "active_orchestrations": len(
            [o for o in _orchestrations.values() if o["status"] in ("pending", "running")]
        ),
        "registered_apps": list(_registered_apps.keys()),
    }, 200


# ── Knowledge Base ────────────────────────────────────────────────────────────


def create_document(body: Dict[str, Any]) -> DispatchResponse:
    """Create a knowledge document."""
    doc_id = body.get("id") or f"doc-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": doc_id,
        "title": body.get("title", ""),
        "doc_type": body.get("doc_type", ""),
        "status": "draft",
        "content": body.get("content", {}),
        "tags": body.get("tags", []),
        "metadata": body.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
        "created_by": body.get("created_by"),
    }
    _documents[doc_id] = doc
    return doc, 201


def get_document(doc_id: str) -> DispatchResponse:
    """Get a knowledge document by ID."""
    doc = _documents.get(doc_id)
    if doc is None:
        return {"error": f"Document '{doc_id}' not found"}, 404
    return doc, 200


def search_documents(
    query: str = "",
    doc_type: str | None = None,
    limit: int = 10,
) -> DispatchResponse:
    """Search knowledge documents."""
    query_lower = query.lower()
    results = list(_documents.values())
    if query_lower:
        results = [
            d for d in results
            if query_lower in d.get("title", "").lower()
            or query_lower in json.dumps(d.get("content", {})).lower()
        ]
    if doc_type:
        results = [d for d in results if d.get("doc_type") == doc_type]
    return {"documents": results[:limit]}, 200


def update_document(doc_id: str, body: Dict[str, Any]) -> DispatchResponse:
    """Update a knowledge document's content."""
    doc = _documents.get(doc_id)
    if doc is None:
        return {"error": f"Document '{doc_id}' not found"}, 404
    doc["content"] = body.get("content", doc["content"])
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return doc, 200


def delete_document(doc_id: str) -> DispatchResponse:
    """Delete a knowledge document."""
    _documents.pop(doc_id, None)
    return None, 204


# ── Risk Registry ─────────────────────────────────────────────────────────────


def register_risk(body: Dict[str, Any]) -> DispatchResponse:
    """Register a new risk."""
    risk_id = body.get("id") or f"risk-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    risk = {
        "id": risk_id,
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "category": body.get("category", "operational"),
        "status": "identified",
        "owner": body.get("owner", "system"),
        "assessment": None,
        "mitigation_plan": None,
        "tags": body.get("tags", []),
        "context": body.get("context", {}),
        "created_at": now,
        "updated_at": now,
    }
    _risks[risk_id] = risk
    return risk, 201


def list_risks(
    status: str | None = None,
    category: str | None = None,
) -> DispatchResponse:
    """List risks with optional filters."""
    results = list(_risks.values())
    if status:
        results = [r for r in results if r["status"] == status]
    if category:
        results = [r for r in results if r["category"] == category]
    return {"risks": results}, 200


def assess_risk(risk_id: str, body: Dict[str, Any]) -> DispatchResponse:
    """Assess a risk."""
    risk = _risks.get(risk_id)
    if risk is None:
        return {"error": f"Risk '{risk_id}' not found"}, 404

    likelihood = body.get("likelihood", 0.5)
    impact = body.get("impact", 0.5)
    score = likelihood * impact
    severity = (
        "critical" if score >= 0.8 else
        "high" if score >= 0.6 else
        "medium" if score >= 0.3 else
        "low" if score >= 0.1 else "info"
    )
    risk["assessment"] = {
        "likelihood": likelihood,
        "impact": impact,
        "severity": severity,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "assessor": body.get("assessor"),
        "notes": body.get("notes"),
    }
    risk["status"] = "assessing"
    risk["updated_at"] = datetime.now(timezone.utc).isoformat()
    return risk, 200


def update_risk_status(risk_id: str, body: Dict[str, Any]) -> DispatchResponse:
    """Update risk status."""
    risk = _risks.get(risk_id)
    if risk is None:
        return {"error": f"Risk '{risk_id}' not found"}, 404
    risk["status"] = body.get("status", risk["status"])
    risk["updated_at"] = datetime.now(timezone.utc).isoformat()
    return risk, 200


def add_mitigation_plan(risk_id: str, body: Dict[str, Any]) -> DispatchResponse:
    """Add a mitigation plan to a risk."""
    risk = _risks.get(risk_id)
    if risk is None:
        return {"error": f"Risk '{risk_id}' not found"}, 404
    risk["mitigation_plan"] = body.get("plan", "")
    risk["status"] = "mitigating"
    risk["updated_at"] = datetime.now(timezone.utc).isoformat()
    return risk, 200


# ── Audit Trail / Decision Ledger ─────────────────────────────────────────────


def log_decision(body: Dict[str, Any]) -> DispatchResponse:
    """Log a decision."""
    record = {
        "id": body.get("id") or f"dec-{uuid.uuid4().hex[:8]}",
        "orchestration_id": body.get("orchestration_id"),
        "agent_id": body.get("agent_id"),
        "decision_type": body.get("decision_type", ""),
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "rationale": body.get("rationale"),
        "outcome": body.get("outcome"),
        "confidence": body.get("confidence"),
        "context": body.get("context", {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _decisions.append(record)
    return record, 201


def get_decision_history(
    orch_id: str | None = None,
    agent_id: str | None = None,
) -> DispatchResponse:
    """Get decision history with optional filters."""
    results = list(_decisions)
    if orch_id:
        results = [d for d in results if d.get("orchestration_id") == orch_id]
    if agent_id:
        results = [d for d in results if d.get("agent_id") == agent_id]
    return {"decisions": results}, 200


def get_audit_trail() -> DispatchResponse:
    """Get the audit trail."""
    return {"entries": _audit_entries}, 200


# ── Covenant Management ───────────────────────────────────────────────────────


def create_covenant(body: Dict[str, Any]) -> DispatchResponse:
    """Create a covenant."""
    cov_id = body.get("id") or f"cov-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    cov = {
        "id": cov_id,
        "title": body.get("title", ""),
        "version": body.get("version", "1.0"),
        "status": "draft",
        "parties": body.get("parties", []),
        "terms": body.get("terms", {}),
        "signers": [],
        "created_at": now,
        "updated_at": now,
    }
    _covenants[cov_id] = cov
    return cov, 201


def list_covenants(status: str | None = None) -> DispatchResponse:
    """List covenants."""
    results = list(_covenants.values())
    if status:
        results = [c for c in results if c["status"] == status]
    return {"covenants": results}, 200


def validate_covenant(cov_id: str) -> DispatchResponse:
    """Validate a covenant."""
    if cov_id not in _covenants:
        return {"error": f"Covenant '{cov_id}' not found"}, 404
    return {
        "covenant_id": cov_id,
        "valid": True,
        "violations": [],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }, 200


def sign_covenant(cov_id: str, body: Dict[str, Any]) -> DispatchResponse:
    """Sign a covenant."""
    cov = _covenants.get(cov_id)
    if cov is None:
        return {"error": f"Covenant '{cov_id}' not found"}, 404
    signer = body.get("signer", "")
    if signer and signer not in cov["signers"]:
        cov["signers"].append(signer)
    cov["updated_at"] = datetime.now(timezone.utc).isoformat()
    return cov, 200


# ── Analytics & Metrics ───────────────────────────────────────────────────────


def record_metric(body: Dict[str, Any]) -> DispatchResponse:
    """Record a metric data point."""
    _metrics_store.append({
        "name": body.get("name", ""),
        "value": body.get("value", 0.0),
        "tags": body.get("tags", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return None, 204


def get_metrics(name: str = "") -> DispatchResponse:
    """Retrieve metric time series."""
    points = [m for m in _metrics_store if m["name"] == name]
    return {
        "name": name,
        "data_points": [
            {"value": p["value"], "tags": p["tags"], "timestamp": p["timestamp"]}
            for p in points
        ],
    }, 200


def create_kpi(body: Dict[str, Any]) -> DispatchResponse:
    """Create a KPI definition."""
    kpi_id = body.get("id") or f"kpi-{uuid.uuid4().hex[:8]}"
    kpi = {
        "id": kpi_id,
        "name": body.get("name", ""),
        "description": body.get("description", ""),
        "target_value": body.get("target_value"),
        "current_value": body.get("current_value"),
        "unit": body.get("unit", ""),
        "metadata": body.get("metadata", {}),
    }
    _kpis[kpi_id] = kpi
    return kpi, 201


def get_kpi_dashboard() -> DispatchResponse:
    """Get the KPI dashboard."""
    return {
        "kpis": list(_kpis.values()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }, 200


# ── MCP Server Integration (proxied) ─────────────────────────────────────────
# These functions proxy to the *aos-mcp-servers* function app (ASISaga/mcp).
# Set MCP_SERVERS_BASE_URL to the deployed aos-mcp-servers URL.
# When the variable is unset a minimal stub response is returned.


async def list_mcp_servers(server_type: str | None = None) -> DispatchResponse:
    """List available MCP servers (proxied to aos-mcp-servers)."""
    if not _MCP_SERVERS_BASE_URL:
        return {"servers": []}, 200
    url = f"{_MCP_SERVERS_BASE_URL}/api/mcp/servers"
    if server_type:
        url += f"?server_type={server_type}"
    return await _proxy_get(url)


async def call_mcp_tool(
    server: str,
    tool: str,
    body: bytes,
) -> DispatchResponse:
    """Invoke a tool on an MCP server (proxied to aos-mcp-servers)."""
    if not _MCP_SERVERS_BASE_URL:
        try:
            args = json.loads(body) if body else {}
        except ValueError:
            args = {}
        return {"server": server, "tool": tool, "args": args, "result": None}, 200
    return await _proxy_post(
        f"{_MCP_SERVERS_BASE_URL}/api/mcp/servers/{server}/tools/{tool}",
        body,
    )


async def get_mcp_server_status(server: str) -> DispatchResponse:
    """Get MCP server status (proxied to aos-mcp-servers)."""
    if not _MCP_SERVERS_BASE_URL:
        return {
            "name": server,
            "status": "running",
            "healthy": True,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }, 200
    return await _proxy_get(f"{_MCP_SERVERS_BASE_URL}/api/mcp/servers/{server}")


# ── Agent Catalog (proxied) & Agent Interaction ───────────────────────────────
# GET /api/agents and GET /api/agents/{id} proxy to *aos-realm-of-agents*
# (ASISaga/realm-of-agents).  Set REALM_OF_AGENTS_BASE_URL accordingly.


async def list_agents(agent_type: str | None = None) -> DispatchResponse:
    """List agents from the realm-of-agents catalog."""
    if not _REALM_OF_AGENTS_BASE_URL:
        return {"agents": list(_foundry_agents.values())}, 200
    url = f"{_REALM_OF_AGENTS_BASE_URL}/api/realm/agents"
    if agent_type:
        url += f"?agent_type={agent_type}"
    return await _proxy_get(url)


async def get_agent_descriptor(agent_id: str) -> DispatchResponse:
    """Get an agent descriptor from the realm-of-agents catalog."""
    if not _REALM_OF_AGENTS_BASE_URL:
        agent = _foundry_agents.get(agent_id)
        if not agent:
            return {"error": f"Agent '{agent_id}' not found"}, 404
        return agent, 200
    return await _proxy_get(f"{_REALM_OF_AGENTS_BASE_URL}/api/realm/agents/{agent_id}")


def ask_agent(agent_id: str, body: Dict[str, Any]) -> DispatchResponse:
    """Direct message to an agent."""
    return {
        "agent_id": agent_id,
        "message": f"Response from {agent_id}",
        "context": body.get("context", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, 200


def send_to_agent(agent_id: str) -> DispatchResponse:  # pylint: disable=unused-argument
    """Fire-and-forget message to an agent."""
    return None, 202


def register_agent(body: Dict[str, Any]) -> DispatchResponse:
    """Register a PurposeDrivenAgent with the Foundry Agent Service."""
    agent_id = body.get("agent_id", "")
    if not agent_id:
        return {"error": "agent_id is required"}, 400

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "agent_id": agent_id,
        "foundry_agent_id": body.get("foundry_agent_id", str(uuid.uuid4())),
        "name": body.get("name", agent_id),
        "purpose": body.get("purpose", ""),
        "adapter_name": body.get("adapter_name", ""),
        "capabilities": body.get("capabilities", []),
        "model": body.get("model", "gpt-4o"),
        "tools": body.get("tools", []),
        "registered_at": now,
        "managed_by": "foundry_agent_service",
    }
    _foundry_agents[agent_id] = record
    logger.info("Registered agent %s with Foundry Agent Service", agent_id)
    return record, 200


def message_agent(agent_id: str, body: Dict[str, Any]) -> DispatchResponse:
    """Send a message to a PurposeDrivenAgent via the Foundry message bridge."""
    message = body.get("message", "")
    if not message:
        return {"error": "message is required"}, 400

    now = datetime.now(timezone.utc).isoformat()
    direction = body.get("direction", "foundry_to_agent")
    record = {
        "message_id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "orchestration_id": body.get("orchestration_id"),
        "content": message,
        "direction": direction,
        "status": "delivered" if direction == "foundry_to_agent" else "sent",
        "timestamp": now,
        "managed_by": "foundry_agent_service",
    }
    logger.info(
        "Message %s bridged: %s → agent %s",
        record["message_id"],
        direction,
        agent_id,
    )
    return record, 200


# ── Network Discovery ─────────────────────────────────────────────────────────


def discover_peers() -> DispatchResponse:
    """Discover peer applications."""
    return {"peers": []}, 200


def join_network(network_id: str) -> DispatchResponse:
    """Join a network."""
    membership = {
        "network_id": network_id,
        "app_id": "caller",
        "joined_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    _network_memberships[network_id] = membership
    return membership, 200


def list_networks() -> DispatchResponse:
    """List available networks."""
    return {"networks": list(_networks.values())}, 200


# ── Internal HTTP Proxy Utilities ─────────────────────────────────────────────


async def _proxy_get(url: str) -> DispatchResponse:
    """Forward a GET request to a downstream function app.

    SSL certificate verification is enforced by the default ``ssl`` context
    (Python standard library default).  The 30-second timeout covers both the
    TCP connection phase and the read phase.

    Args:
        url: Full URL of the downstream endpoint.

    Returns:
        ``(body_bytes, status_code)`` — body is the raw upstream response bytes.
        Returns ``(error_dict, 503)`` when the upstream is unreachable and
        ``(error_dict, 504)`` on timeout.
    """
    loop = asyncio.get_running_loop()
    try:
        def _do_get() -> tuple[int, bytes]:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.status, resp.read()

        status, body = await loop.run_in_executor(None, _do_get)
        return body, status
    except urllib.error.HTTPError as exc:
        return exc.read(), exc.code
    except TimeoutError as exc:
        logger.warning("Proxy GET %s timed out: %s", url, exc)
        return {"error": "Upstream service timed out"}, 504
    except urllib.error.URLError as exc:
        logger.warning("Proxy GET %s network error: %s", url, exc.reason)
        return {"error": f"Upstream network error: {exc.reason}"}, 503
    except OSError as exc:
        logger.warning("Proxy GET %s OS error: %s", url, exc)
        return {"error": f"Upstream service unavailable: {exc}"}, 503


async def _proxy_post(url: str, body: bytes) -> DispatchResponse:
    """Forward a POST request to a downstream function app.

    SSL certificate verification is enforced by the default ``ssl`` context
    (Python standard library default).  The 30-second timeout covers both the
    TCP connection phase and the read phase.

    Args:
        url:  Full URL of the downstream endpoint.
        body: Raw request body bytes.

    Returns:
        ``(body_bytes, status_code)`` — body is the raw upstream response bytes.
        Returns ``(error_dict, 503)`` when the upstream is unreachable and
        ``(error_dict, 504)`` on timeout.
    """
    loop = asyncio.get_running_loop()
    req_obj = urllib.request.Request(url, data=body, method="POST")
    req_obj.add_header("Content-Type", "application/json")
    try:
        def _do_post() -> tuple[int, bytes]:
            with urllib.request.urlopen(req_obj, timeout=30) as resp:
                return resp.status, resp.read()

        status, resp_body = await loop.run_in_executor(None, _do_post)
        return resp_body, status
    except urllib.error.HTTPError as exc:
        return exc.read(), exc.code
    except TimeoutError as exc:
        logger.warning("Proxy POST %s timed out: %s", url, exc)
        return {"error": "Upstream service timed out"}, 504
    except urllib.error.URLError as exc:
        logger.warning("Proxy POST %s network error: %s", url, exc.reason)
        return {"error": f"Upstream network error: {exc.reason}"}, 503
    except OSError as exc:
        logger.warning("Proxy POST %s OS error: %s", url, exc)
        return {"error": f"Upstream service unavailable: {exc}"}, 503
