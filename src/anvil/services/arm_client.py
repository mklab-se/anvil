"""ARM client service for Azure Resource Manager operations."""

import re
from dataclasses import dataclass
from typing import Any

import httpx
from azure.core.credentials import TokenCredential

from anvil.services.exceptions import NetworkError, NotAuthenticated


@dataclass
class PublishedAgent:
    """Published agent information."""

    agent_name: str
    application_name: str
    base_url: str
    is_enabled: bool
    protocols: list[str]  # ["Responses", "ActivityProtocol"]
    state: str  # "Running", "Stopped", etc.
    deployment_name: str


class ArmClientService:
    """Service for Azure Resource Manager operations.

    Provides methods for managing published agents via the ARM API,
    which is separate from the Azure AI Projects SDK.
    """

    # ARM API version for Cognitive Services
    API_VERSION = "2025-10-01-preview"

    def __init__(
        self,
        subscription_id: str,
        resource_group: str,
        account_name: str,
        project_name: str,
        credential: TokenCredential,
    ) -> None:
        """Initialize the ARM client service.

        Args:
            subscription_id: Azure subscription ID.
            resource_group: Resource group name.
            account_name: Cognitive Services account name.
            project_name: Project name within the account.
            credential: Azure credential for authentication.
        """
        self._subscription_id = subscription_id
        self._resource_group = resource_group
        self._account_name = account_name
        self._project_name = project_name
        self._credential = credential
        self._base_url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group}"
            f"/providers/Microsoft.CognitiveServices"
            f"/accounts/{account_name}/projects/{project_name}"
        )

    @classmethod
    def from_project_endpoint(
        cls,
        project_endpoint: str,
        subscription_id: str,
        resource_group: str,
        credential: TokenCredential,
    ) -> "ArmClientService":
        """Create an ARM client from a project endpoint URL.

        Args:
            project_endpoint: Project endpoint URL (e.g., https://account.services.ai.azure.com/api/projects/proj-name)
            subscription_id: Azure subscription ID.
            resource_group: Resource group name.
            credential: Azure credential for authentication.

        Returns:
            Configured ArmClientService instance.
        """
        # Parse endpoint to extract account and project names
        # Format: https://{account}.services.ai.azure.com/api/projects/{project}
        match = re.match(
            r"https://([^.]+)\.services\.ai\.azure\.com/api/projects/([^/]+)",
            project_endpoint,
        )
        if not match:
            raise ValueError(f"Invalid project endpoint format: {project_endpoint}")

        account_name = match.group(1)
        project_name = match.group(2)

        return cls(
            subscription_id=subscription_id,
            resource_group=resource_group,
            account_name=account_name,
            project_name=project_name,
            credential=credential,
        )

    def _get_access_token(self) -> str:
        """Get an access token for ARM API."""
        token = self._credential.get_token("https://management.azure.com/.default")
        return token.token

    def _make_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to ARM API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path relative to project.
            json_body: Optional JSON body for the request.

        Returns:
            Response JSON as a dictionary.

        Raises:
            NotAuthenticated: If authentication fails.
            NetworkError: If the request fails.
        """
        url = f"{self._base_url}{path}?api-version={self.API_VERSION}"
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "DELETE":
                    response = client.delete(url, headers=headers)
                elif method == "PUT":
                    response = client.put(url, headers=headers, json=json_body)
                elif method == "POST":
                    response = client.post(url, headers=headers, json=json_body)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if response.status_code == 401:
                    raise NotAuthenticated("ARM API authentication failed")
                if response.status_code == 204:
                    return {}  # No content response
                if response.status_code >= 400:
                    error_msg = response.text
                    raise NetworkError(f"ARM API request failed: {error_msg}")

                return response.json() if response.text else {}
        except httpx.RequestError as e:
            raise NetworkError(f"ARM API request failed: {e}") from e

    def list_published_agents(self) -> list[PublishedAgent]:
        """List all published agents in the project.

        Returns:
            List of PublishedAgent objects with publishing details.

        Raises:
            NotAuthenticated: If authentication fails.
            NetworkError: If the request fails.
        """
        published_agents: list[PublishedAgent] = []

        try:
            # Get all applications
            apps_response = self._make_request("GET", "/applications")
            applications = apps_response.get("value", [])

            for app in applications:
                app_name = app.get("name", "")
                props = app.get("properties", {})
                base_url = props.get("baseUrl", "")
                is_enabled = props.get("isEnabled", False)

                # Get the agents associated with this application
                app_agents = props.get("agents", [])
                if not app_agents:
                    continue

                # Get deployments for this application to get protocols and state
                try:
                    deployments_response = self._make_request(
                        "GET", f"/applications/{app_name}/agentdeployments"
                    )
                    deployments = deployments_response.get("value", [])
                except NetworkError:
                    deployments = []

                for agent_info in app_agents:
                    agent_name = agent_info.get("agentName", "")
                    if not agent_name:
                        continue

                    # Find matching deployment for protocols and state
                    protocols: list[str] = []
                    state = "Unknown"
                    deployment_name = ""

                    for deployment in deployments:
                        dep_props = deployment.get("properties", {})
                        dep_agents = dep_props.get("agents", [])

                        # Check if this deployment contains our agent
                        for dep_agent in dep_agents:
                            if dep_agent.get("agentName") == agent_name:
                                deployment_name = deployment.get("name", "")
                                state = dep_props.get("state", "Unknown")

                                # Extract protocol names
                                for proto in dep_props.get("protocols", []):
                                    proto_name = proto.get("protocol", "")
                                    if proto_name:
                                        protocols.append(proto_name)
                                break

                    published_agents.append(
                        PublishedAgent(
                            agent_name=agent_name,
                            application_name=app_name,
                            base_url=base_url,
                            is_enabled=is_enabled,
                            protocols=protocols,
                            state=state,
                            deployment_name=deployment_name,
                        )
                    )

        except NotAuthenticated:
            raise
        except Exception as e:
            raise NetworkError(f"Failed to list published agents: {e}") from e

        return published_agents

    def get_published_agent(self, agent_name: str) -> PublishedAgent | None:
        """Get publishing info for a specific agent.

        Args:
            agent_name: Name of the agent to look up.

        Returns:
            PublishedAgent if found, None otherwise.
        """
        published = self.list_published_agents()
        for agent in published:
            if agent.agent_name == agent_name:
                return agent
        return None

    def unpublish_agent(self, application_name: str, deployment_name: str) -> None:
        """Unpublish an agent by deleting its deployment.

        Args:
            application_name: Name of the application.
            deployment_name: Name of the deployment to delete.

        Raises:
            NotAuthenticated: If authentication fails.
            NetworkError: If the request fails.
        """
        self._make_request(
            "DELETE",
            f"/applications/{application_name}/agentdeployments/{deployment_name}",
        )
