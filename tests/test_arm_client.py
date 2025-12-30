"""Tests for ArmClientService - ARM API operations."""

from unittest.mock import MagicMock, patch

import pytest

from anvil.services.arm_client import ArmClientService, PublishedAgent
from anvil.services.exceptions import NetworkError, NotAuthenticated


class TestArmClientServiceInit:
    """Tests for ArmClientService initialization."""

    def test_init_with_all_parameters(self):
        """Test initialization with all required parameters."""
        mock_cred = MagicMock()
        service = ArmClientService(
            subscription_id="sub-123",
            resource_group="rg-test",
            account_name="test-account",
            project_name="proj-default",
            credential=mock_cred,
        )

        assert service._subscription_id == "sub-123"
        assert service._resource_group == "rg-test"
        assert service._account_name == "test-account"
        assert service._project_name == "proj-default"

    def test_base_url_construction(self):
        """Test that base URL is constructed correctly."""
        mock_cred = MagicMock()
        service = ArmClientService(
            subscription_id="sub-123",
            resource_group="rg-test",
            account_name="test-account",
            project_name="proj-default",
            credential=mock_cred,
        )

        expected = (
            "https://management.azure.com/subscriptions/sub-123"
            "/resourceGroups/rg-test"
            "/providers/Microsoft.CognitiveServices"
            "/accounts/test-account/projects/proj-default"
        )
        assert service._base_url == expected


class TestFromProjectEndpoint:
    """Tests for from_project_endpoint factory method."""

    def test_parses_valid_endpoint(self):
        """Test parsing a valid project endpoint URL."""
        mock_cred = MagicMock()
        endpoint = "https://my-foundry.services.ai.azure.com/api/projects/my-project"

        service = ArmClientService.from_project_endpoint(
            project_endpoint=endpoint,
            subscription_id="sub-123",
            resource_group="rg-test",
            credential=mock_cred,
        )

        assert service._account_name == "my-foundry"
        assert service._project_name == "my-project"

    def test_raises_for_invalid_endpoint(self):
        """Test that invalid endpoint raises ValueError."""
        mock_cred = MagicMock()
        invalid_endpoint = "https://invalid.url/path"

        with pytest.raises(ValueError, match="Invalid project endpoint format"):
            ArmClientService.from_project_endpoint(
                project_endpoint=invalid_endpoint,
                subscription_id="sub-123",
                resource_group="rg-test",
                credential=mock_cred,
            )

    def test_parses_endpoint_with_complex_names(self):
        """Test parsing endpoint with hyphens and numbers."""
        mock_cred = MagicMock()
        endpoint = "https://irma-test-foundry.services.ai.azure.com/api/projects/proj-default"

        service = ArmClientService.from_project_endpoint(
            project_endpoint=endpoint,
            subscription_id="sub-123",
            resource_group="rg-test",
            credential=mock_cred,
        )

        assert service._account_name == "irma-test-foundry"
        assert service._project_name == "proj-default"


class TestPublishedAgentDataclass:
    """Tests for PublishedAgent dataclass."""

    def test_published_agent_has_all_fields(self):
        """Test that PublishedAgent has all required fields."""
        from anvil.services.arm_client import PublishedDeployment

        deployment = PublishedDeployment(
            deployment_name="test-deployment",
            state="Running",
            protocols=["Responses"],
        )
        pub = PublishedAgent(
            agent_name="test-agent",
            application_name="test-app",
            base_url="https://test.url",
            is_enabled=True,
            deployments=[deployment],
        )

        assert pub.agent_name == "test-agent"
        assert pub.application_name == "test-app"
        assert pub.base_url == "https://test.url"
        assert pub.is_enabled is True
        # Test backward-compatible properties
        assert pub.protocols == ["Responses"]
        assert pub.state == "Running"
        assert pub.deployment_name == "test-deployment"
        assert pub.has_multiple_deployments is False

    def test_published_agent_multiple_deployments(self):
        """Test PublishedAgent with multiple deployments."""
        from anvil.services.arm_client import PublishedDeployment

        dep1 = PublishedDeployment(
            deployment_name="deploy-1", state="Running", protocols=["Responses"]
        )
        dep2 = PublishedDeployment(
            deployment_name="deploy-2", state="Stopped", protocols=["ActivityProtocol"]
        )
        pub = PublishedAgent(
            agent_name="multi-agent",
            application_name="app",
            base_url="https://test.url",
            is_enabled=True,
            deployments=[dep1, dep2],
        )

        assert pub.has_multiple_deployments is True
        assert len(pub.deployments) == 2
        # Properties return first deployment's values
        assert pub.state == "Running"
        assert pub.protocols == ["Responses"]
        assert pub.deployment_name == "deploy-1"


class TestListPublishedAgents:
    """Tests for list_published_agents method."""

    @pytest.fixture
    def service(self):
        """Create an ArmClientService for testing."""
        mock_cred = MagicMock()
        mock_cred.get_token.return_value = MagicMock(token="test-token")
        return ArmClientService(
            subscription_id="sub-123",
            resource_group="rg-test",
            account_name="test-account",
            project_name="proj-default",
            credential=mock_cred,
        )

    @patch("anvil.services.arm_client.httpx.Client")
    def test_returns_published_agents(self, mock_httpx, service):
        """Test listing published agents."""
        # Mock the applications response
        apps_response = MagicMock()
        apps_response.status_code = 200
        apps_response.text = '{"value": []}'
        apps_response.json.return_value = {
            "value": [
                {
                    "name": "my-app",
                    "properties": {
                        "baseUrl": "https://test.url/api",
                        "isEnabled": True,
                        "agents": [{"agentName": "my-agent"}],
                    },
                }
            ]
        }

        # Mock the deployments response
        deployments_response = MagicMock()
        deployments_response.status_code = 200
        deployments_response.text = '{"value": []}'
        deployments_response.json.return_value = {
            "value": [
                {
                    "name": "my-deployment",
                    "properties": {
                        "agents": [{"agentName": "my-agent"}],
                        "protocols": [{"protocol": "Responses", "version": "1.0"}],
                        "state": "Running",
                    },
                }
            ]
        }

        # Configure mock client to return different responses
        mock_client_instance = MagicMock()

        def mock_get(url, headers):
            if "/applications?" in url:
                return apps_response
            if "/agentdeployments?" in url:
                return deployments_response
            return apps_response

        mock_client_instance.get.side_effect = mock_get
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        published = service.list_published_agents()

        assert len(published) == 1
        assert published[0].agent_name == "my-agent"
        assert published[0].application_name == "my-app"
        assert published[0].base_url == "https://test.url/api"
        assert published[0].protocols == ["Responses"]
        assert published[0].state == "Running"

    @patch("anvil.services.arm_client.httpx.Client")
    def test_returns_empty_list_when_no_applications(self, mock_httpx, service):
        """Test returning empty list when no applications exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"value": []}'
        mock_response.json.return_value = {"value": []}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        published = service.list_published_agents()

        assert published == []

    @patch("anvil.services.arm_client.httpx.Client")
    def test_raises_not_authenticated_on_401(self, mock_httpx, service):
        """Test that 401 response raises NotAuthenticated."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        with pytest.raises(NotAuthenticated):
            service.list_published_agents()


class TestGetPublishedAgent:
    """Tests for get_published_agent method."""

    @pytest.fixture
    def service(self):
        """Create an ArmClientService for testing."""
        mock_cred = MagicMock()
        mock_cred.get_token.return_value = MagicMock(token="test-token")
        return ArmClientService(
            subscription_id="sub-123",
            resource_group="rg-test",
            account_name="test-account",
            project_name="proj-default",
            credential=mock_cred,
        )

    @patch("anvil.services.arm_client.httpx.Client")
    def test_returns_agent_when_found(self, mock_httpx, service):
        """Test finding a specific published agent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"value": []}'
        mock_response.json.return_value = {
            "value": [
                {
                    "name": "my-app",
                    "properties": {
                        "baseUrl": "https://test.url",
                        "isEnabled": True,
                        "agents": [{"agentName": "target-agent"}],
                    },
                }
            ]
        }

        deployments_response = MagicMock()
        deployments_response.status_code = 200
        deployments_response.text = '{"value": []}'
        deployments_response.json.return_value = {"value": []}

        mock_client_instance = MagicMock()

        def mock_get(url, headers):
            if "/applications?" in url:
                return mock_response
            return deployments_response

        mock_client_instance.get.side_effect = mock_get
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        result = service.get_published_agent("target-agent")

        assert result is not None
        assert result.agent_name == "target-agent"

    @patch("anvil.services.arm_client.httpx.Client")
    def test_returns_none_when_not_found(self, mock_httpx, service):
        """Test returning None when agent not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"value": []}'
        mock_response.json.return_value = {"value": []}

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        result = service.get_published_agent("nonexistent-agent")

        assert result is None


class TestUnpublishAgent:
    """Tests for unpublish_agent method."""

    @pytest.fixture
    def service(self):
        """Create an ArmClientService for testing."""
        mock_cred = MagicMock()
        mock_cred.get_token.return_value = MagicMock(token="test-token")
        return ArmClientService(
            subscription_id="sub-123",
            resource_group="rg-test",
            account_name="test-account",
            project_name="proj-default",
            credential=mock_cred,
        )

    @patch("anvil.services.arm_client.httpx.Client")
    def test_unpublish_calls_delete(self, mock_httpx, service):
        """Test that unpublish calls DELETE on the correct endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""

        mock_client_instance = MagicMock()
        mock_client_instance.delete.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        # Should not raise
        service.unpublish_agent("my-app", "my-deployment")

        # Verify DELETE was called
        mock_client_instance.delete.assert_called_once()
        call_url = mock_client_instance.delete.call_args[0][0]
        assert "/applications/my-app/agentdeployments/my-deployment" in call_url

    @patch("anvil.services.arm_client.httpx.Client")
    def test_unpublish_raises_on_error(self, mock_httpx, service):
        """Test that unpublish raises NetworkError on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client_instance = MagicMock()
        mock_client_instance.delete.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        with pytest.raises(NetworkError):
            service.unpublish_agent("my-app", "my-deployment")
