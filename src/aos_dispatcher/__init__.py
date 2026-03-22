"""AOS Dispatcher — pure Python dispatcher library for the Agent Operating System.

Framework-agnostic core dispatcher with no dependency on ``azure.functions``.
Import this package to use the dispatcher logic in any hosting environment
(Azure Functions, FastAPI, gRPC, etc.).

Example usage::

    from aos_dispatcher import dispatcher

    # Process an orchestration request
    body, status = dispatcher.process_orchestration_request({
        "agent_ids": ["ceo", "cfo"],
        "workflow": "collaborative",
        "task": {"type": "strategic_review"},
    })
"""

from __future__ import annotations

from aos_dispatcher.dispatcher import (
    # Configuration
    _MCP_SERVERS_BASE_URL,
    _REALM_OF_AGENTS_BASE_URL,
    # In-memory stores (exposed for testing)
    _orchestrations,
    _registered_apps,
    _foundry_agents,
    # Orchestrations
    process_orchestration_request,
    get_orchestration_status,
    get_orchestration_result,
    cancel_orchestration,
    # App Registration
    register_app,
    get_app_registration,
    deregister_app,
    # Health
    health,
    # Knowledge Base
    create_document,
    get_document,
    search_documents,
    update_document,
    delete_document,
    # Risk Registry
    register_risk,
    list_risks,
    assess_risk,
    update_risk_status,
    add_mitigation_plan,
    # Audit Trail
    log_decision,
    get_decision_history,
    get_audit_trail,
    # Covenants
    create_covenant,
    list_covenants,
    validate_covenant,
    sign_covenant,
    # Analytics
    record_metric,
    get_metrics,
    create_kpi,
    get_kpi_dashboard,
    # MCP (proxied)
    list_mcp_servers,
    call_mcp_tool,
    get_mcp_server_status,
    # Agents
    list_agents,
    get_agent_descriptor,
    ask_agent,
    send_to_agent,
    register_agent,
    message_agent,
    # Network
    discover_peers,
    join_network,
    list_networks,
)

__all__ = [
    # Configuration
    "_MCP_SERVERS_BASE_URL",
    "_REALM_OF_AGENTS_BASE_URL",
    # In-memory stores
    "_orchestrations",
    "_registered_apps",
    "_foundry_agents",
    # Orchestrations
    "process_orchestration_request",
    "get_orchestration_status",
    "get_orchestration_result",
    "cancel_orchestration",
    # App Registration
    "register_app",
    "get_app_registration",
    "deregister_app",
    # Health
    "health",
    # Knowledge Base
    "create_document",
    "get_document",
    "search_documents",
    "update_document",
    "delete_document",
    # Risk Registry
    "register_risk",
    "list_risks",
    "assess_risk",
    "update_risk_status",
    "add_mitigation_plan",
    # Audit Trail
    "log_decision",
    "get_decision_history",
    "get_audit_trail",
    # Covenants
    "create_covenant",
    "list_covenants",
    "validate_covenant",
    "sign_covenant",
    # Analytics
    "record_metric",
    "get_metrics",
    "create_kpi",
    "get_kpi_dashboard",
    # MCP
    "list_mcp_servers",
    "call_mcp_tool",
    "get_mcp_server_status",
    # Agents
    "list_agents",
    "get_agent_descriptor",
    "ask_agent",
    "send_to_agent",
    "register_agent",
    "message_agent",
    # Network
    "discover_peers",
    "join_network",
    "list_networks",
]
