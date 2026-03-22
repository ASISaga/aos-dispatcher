"""Tests for the AOS Dispatcher library (aos_dispatcher).

Tests the orchestration API, app registration, and proxy fallback behaviour
directly against the pure Python dispatcher module — no azure.functions
dependency required.
"""
import json
import pytest

import aos_dispatcher.dispatcher as dispatcher


class TestDispatcher:
    """Core dispatcher tests."""

    def test_health(self):
        """Test health check returns expected structure."""
        body, status = dispatcher.health()
        assert status == 200
        assert body["app"] == "aos-dispatcher"
        assert body["status"] == "healthy"
        assert isinstance(body["active_orchestrations"], int)

    def test_process_orchestration_request(self):
        """Test orchestration request processing."""
        body = {
            "agent_ids": ["ceo", "cfo"],
            "workflow": "collaborative",
            "task": {"type": "test"},
        }
        result, status = dispatcher.process_orchestration_request(body)
        assert status == 202
        assert result["status"] == "pending"
        assert result["agent_ids"] == ["ceo", "cfo"]

        # Verify it was stored
        assert result["orchestration_id"] in dispatcher._orchestrations

    def test_process_orchestration_request_empty_agents(self):
        """Test orchestration request with empty agents list."""
        body = {"agent_ids": [], "task": {"type": "test"}}
        result, status = dispatcher.process_orchestration_request(body)
        assert status == 400
        assert "error" in result

    def test_process_orchestration_request_with_source_app(self):
        """Test orchestration request from Service Bus with source app."""
        body = {
            "agent_ids": ["cmo"],
            "task": {"type": "market_analysis"},
        }
        result, status = dispatcher.process_orchestration_request(body, source_app="business-infinity")
        assert status == 202

        orch_id = result["orchestration_id"]
        assert dispatcher._orchestrations[orch_id]["source_app"] == "business-infinity"

    def test_registered_apps_store(self):
        """Test app registration store."""
        dispatcher._registered_apps["test-app"] = {
            "app_name": "test-app",
            "workflows": ["test-workflow"],
            "status": "provisioned",
        }
        assert "test-app" in dispatcher._registered_apps
        del dispatcher._registered_apps["test-app"]

    def test_stores_are_dicts(self):
        """Test that in-memory stores are correctly typed."""
        assert isinstance(dispatcher._orchestrations, dict)
        assert isinstance(dispatcher._registered_apps, dict)


class TestProxyFallbacks:
    """Tests for MCP and agent-catalog proxy endpoints in stub/fallback mode."""

    def test_base_urls_not_set_by_default(self):
        """MCP_SERVERS_BASE_URL and REALM_OF_AGENTS_BASE_URL are empty by default."""
        assert dispatcher._MCP_SERVERS_BASE_URL == ""
        assert dispatcher._REALM_OF_AGENTS_BASE_URL == ""

    async def test_list_mcp_servers_fallback(self):
        """list_mcp_servers returns empty list when MCP_SERVERS_BASE_URL is unset."""
        original = dispatcher._MCP_SERVERS_BASE_URL
        dispatcher._MCP_SERVERS_BASE_URL = ""
        try:
            body, status = await dispatcher.list_mcp_servers()
            assert status == 200
            assert body == {"servers": []}
        finally:
            dispatcher._MCP_SERVERS_BASE_URL = original

    async def test_list_agents_fallback(self):
        """list_agents returns in-memory agents when REALM_OF_AGENTS_BASE_URL is unset."""
        original = dispatcher._REALM_OF_AGENTS_BASE_URL
        dispatcher._REALM_OF_AGENTS_BASE_URL = ""
        try:
            body, status = await dispatcher.list_agents()
            assert status == 200
            assert "agents" in body
        finally:
            dispatcher._REALM_OF_AGENTS_BASE_URL = original

    async def test_get_agent_descriptor_fallback_not_found(self):
        """get_agent_descriptor returns 404 for unknown agents when base URL is unset."""
        original = dispatcher._REALM_OF_AGENTS_BASE_URL
        dispatcher._REALM_OF_AGENTS_BASE_URL = ""
        try:
            body, status = await dispatcher.get_agent_descriptor("unknown-agent")
            assert status == 404
            assert "error" in body
        finally:
            dispatcher._REALM_OF_AGENTS_BASE_URL = original

    async def test_call_mcp_tool_fallback(self):
        """call_mcp_tool returns stub response when MCP_SERVERS_BASE_URL is unset."""
        original = dispatcher._MCP_SERVERS_BASE_URL
        dispatcher._MCP_SERVERS_BASE_URL = ""
        try:
            body, status = await dispatcher.call_mcp_tool(
                "test-server", "test-tool", b'{"param": "value"}'
            )
            assert status == 200
            assert body["server"] == "test-server"
            assert body["tool"] == "test-tool"
        finally:
            dispatcher._MCP_SERVERS_BASE_URL = original
