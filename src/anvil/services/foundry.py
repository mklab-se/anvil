"""Microsoft Foundry service for Anvil."""

import re
from dataclasses import dataclass

from azure.ai.projects import AIProjectClient
from azure.core.credentials import TokenCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

from anvil.services.exceptions import NetworkError, NotAuthenticated, ResourceNotFound


@dataclass
class FoundryAccount:
    """Azure AI Foundry account information."""

    id: str
    name: str
    resource_group: str
    location: str
    endpoint: str


@dataclass
class FoundryProject:
    """Azure AI Foundry project information."""

    id: str
    name: str
    display_name: str
    endpoint: str


class FoundryService:
    """Lists Foundry accounts and projects."""

    def __init__(self, credential: TokenCredential, subscription_id: str) -> None:
        """Initialize the foundry service.

        Args:
            credential: Azure credential for authentication.
            subscription_id: Azure subscription ID.
        """
        self._credential = credential
        self._subscription_id = subscription_id

    def _extract_resource_group(self, resource_id: str) -> str:
        """Extract resource group name from Azure resource ID.

        Args:
            resource_id: Full Azure resource ID.

        Returns:
            Resource group name.
        """
        match = re.search(r"/resourceGroups/([^/]+)/", resource_id)
        return match.group(1) if match else ""

    def list_accounts(self) -> list[FoundryAccount]:
        """List AI Foundry accounts (kind=AIServices) in subscription.

        Returns:
            List of Foundry accounts.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            client = CognitiveServicesManagementClient(
                credential=self._credential,
                subscription_id=self._subscription_id,
            )

            accounts: list[FoundryAccount] = []

            for account in client.accounts.list():
                # Filter for AIServices kind (Foundry accounts)
                if account.kind and account.kind.lower() == "aiservices":
                    accounts.append(
                        FoundryAccount(
                            id=account.id or "",
                            name=account.name or "",
                            resource_group=self._extract_resource_group(account.id or ""),
                            location=account.location or "",
                            endpoint=(
                                account.properties.endpoint
                                if account.properties and account.properties.endpoint
                                else ""
                            ),
                        )
                    )

            return accounts
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            raise NetworkError(f"Failed to list Foundry accounts: {e}") from e

    def list_projects(self, resource_group: str, account_name: str) -> list[FoundryProject]:
        """List projects within a Foundry account.

        Args:
            resource_group: Resource group name.
            account_name: Foundry account name.

        Returns:
            List of projects.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
            ResourceNotFound: If account not found.
        """
        try:
            client = CognitiveServicesManagementClient(
                credential=self._credential,
                subscription_id=self._subscription_id,
            )

            projects: list[FoundryProject] = []

            for project in client.projects.list(
                resource_group_name=resource_group,
                account_name=account_name,
            ):
                # Extract endpoint from properties
                endpoint = ""
                if project.properties:
                    endpoints = getattr(project.properties, "endpoints", None)
                    if endpoints and isinstance(endpoints, dict):
                        # Get the first endpoint
                        endpoint = next(iter(endpoints.values()), "")

                # Get display name, falling back to project name
                display_name = project.name or ""
                if project.properties and hasattr(project.properties, "display_name"):
                    display_name = project.properties.display_name or project.name or ""

                projects.append(
                    FoundryProject(
                        id=project.id or "",
                        name=project.name or "",
                        display_name=display_name,
                        endpoint=endpoint,
                    )
                )

            return projects
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            if e.status_code == 404:
                raise ResourceNotFound(
                    f"Account '{account_name}' not found in resource group '{resource_group}'"
                ) from e
            raise NetworkError(f"Failed to list projects: {e}") from e

    def create_project_client(self, project_endpoint: str) -> AIProjectClient:
        """Create AIProjectClient for data plane operations.

        Args:
            project_endpoint: The project endpoint URL.

        Returns:
            Configured AIProjectClient.
        """
        return AIProjectClient(
            endpoint=project_endpoint,
            credential=self._credential,
        )
