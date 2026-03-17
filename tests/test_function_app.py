"""Tests for the AOS Dispatcher.

Tests the orchestration API, Service Bus trigger, and app registration endpoints.
"""
import json
import pytest


class TestFunctionApp:
    """AOS Function App tests."""

    def test_health_endpoint(self):
        """Test health check HTTP endpoint."""
        from function_app import _orchestrations, _registered_apps

        assert isinstance(_orchestrations, dict)
        assert isinstance(_registered_apps, dict)

    def test_process_orchestration_request(self):
        """Test orchestration request processing."""
        from function_app import _process_orchestration_request, _orchestrations

        body = {
            "agent_ids": ["ceo", "cfo"],
            "workflow": "collaborative",
            "task": {"type": "test"},
        }
        response = _process_orchestration_request(body)
        assert response.status_code == 202

        data = json.loads(response.get_body())
        assert data["status"] == "pending"
        assert data["agent_ids"] == ["ceo", "cfo"]

        # Verify it was stored
        assert data["orchestration_id"] in _orchestrations

    def test_process_orchestration_request_empty_agents(self):
        """Test orchestration request with empty agents list."""
        from function_app import _process_orchestration_request

        body = {"agent_ids": [], "task": {"type": "test"}}
        response = _process_orchestration_request(body)
        assert response.status_code == 400

    def test_process_orchestration_request_with_source_app(self):
        """Test orchestration request from Service Bus with source app."""
        from function_app import _process_orchestration_request, _orchestrations

        body = {
            "agent_ids": ["cmo"],
            "task": {"type": "market_analysis"},
        }
        response = _process_orchestration_request(body, source_app="business-infinity")
        assert response.status_code == 202

        data = json.loads(response.get_body())
        orch_id = data["orchestration_id"]
        assert _orchestrations[orch_id]["source_app"] == "business-infinity"

    def test_registered_apps_store(self):
        """Test app registration store."""
        from function_app import _registered_apps

        _registered_apps["test-app"] = {
            "app_name": "test-app",
            "workflows": ["test-workflow"],
            "status": "provisioned",
        }
        assert "test-app" in _registered_apps
        del _registered_apps["test-app"]


class TestProxyFallbacks:
    """Tests for MCP and agent-catalog proxy endpoints in stub/fallback mode."""

    def test_mcp_servers_base_url_not_set(self):
        """MCP_SERVERS_BASE_URL and REALM_OF_AGENTS_BASE_URL are empty by default."""
        import function_app

        assert function_app._MCP_SERVERS_BASE_URL == ""
        assert function_app._REALM_OF_AGENTS_BASE_URL == ""

    async def test_list_mcp_servers_fallback(self):
        """list_mcp_servers returns empty list when MCP_SERVERS_BASE_URL is unset."""
        import function_app

        # Ensure no base URL is configured
        original = function_app._MCP_SERVERS_BASE_URL
        function_app._MCP_SERVERS_BASE_URL = ""
        try:
            req = _make_request(method="GET")
            response = await function_app.list_mcp_servers(req)
            assert response.status_code == 200
            data = json.loads(response.get_body())
            assert data == {"servers": []}
        finally:
            function_app._MCP_SERVERS_BASE_URL = original

    async def test_list_agents_fallback(self):
        """list_agents returns in-memory agents when REALM_OF_AGENTS_BASE_URL is unset."""
        import function_app

        original = function_app._REALM_OF_AGENTS_BASE_URL
        function_app._REALM_OF_AGENTS_BASE_URL = ""
        try:
            req = _make_request(method="GET")
            response = await function_app.list_agents(req)
            assert response.status_code == 200
            data = json.loads(response.get_body())
            assert "agents" in data
        finally:
            function_app._REALM_OF_AGENTS_BASE_URL = original

    async def test_get_agent_descriptor_fallback_not_found(self):
        """get_agent_descriptor returns 404 for unknown agents when base URL is unset."""
        import function_app

        original = function_app._REALM_OF_AGENTS_BASE_URL
        function_app._REALM_OF_AGENTS_BASE_URL = ""
        try:
            req = _make_request(method="GET", route_params={"agent_id": "unknown-agent"})
            response = await function_app.get_agent_descriptor(req)
            assert response.status_code == 404
            data = json.loads(response.get_body())
            assert "error" in data
        finally:
            function_app._REALM_OF_AGENTS_BASE_URL = original

    async def test_call_mcp_tool_fallback(self):
        """call_mcp_tool returns stub response when MCP_SERVERS_BASE_URL is unset."""
        import function_app

        original = function_app._MCP_SERVERS_BASE_URL
        function_app._MCP_SERVERS_BASE_URL = ""
        try:
            req = _make_request(
                method="POST",
                body=b'{"param": "value"}',
                route_params={"server": "test-server", "tool": "test-tool"},
            )
            response = await function_app.call_mcp_tool(req)
            assert response.status_code == 200
            data = json.loads(response.get_body())
            assert data["server"] == "test-server"
            assert data["tool"] == "test-tool"
        finally:
            function_app._MCP_SERVERS_BASE_URL = original


# ── Test helpers ──────────────────────────────────────────────────────────────


def _make_request(
    method: str = "GET",
    body: bytes = b"",
    route_params: dict | None = None,
    params: dict | None = None,
) -> "FakeRequest":
    """Build a minimal fake HttpRequest for unit tests."""
    return FakeRequest(
        method=method,
        body=body,
        route_params=route_params or {},
        params=params or {},
    )


class FakeRequest:
    """Minimal stand-in for azure.functions.HttpRequest."""

    def __init__(
        self,
        method: str,
        body: bytes,
        route_params: dict,
        params: dict,
    ) -> None:
        self.method = method
        self._body = body
        self.route_params = route_params
        self.params = params

    def get_body(self) -> bytes:
        return self._body

    def get_json(self):
        return json.loads(self._body) if self._body else {}
