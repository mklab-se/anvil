"""Project client service for Azure AI Projects SDK operations."""

from dataclasses import dataclass
from datetime import datetime

from azure.ai.projects import AIProjectClient
from azure.core.credentials import TokenCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

from anvil.services.exceptions import NetworkError, NotAuthenticated


@dataclass
class Agent:
    """Agent information."""

    id: str
    name: str
    agent_type: str
    created_at: datetime | None
    instructions: str | None
    model: str | None


@dataclass
class Deployment:
    """Model deployment information."""

    name: str
    model: str
    version: str
    status: str


class ProjectClientService:
    """Service for Azure AI Projects SDK data plane operations.

    Provides methods for listing and managing agents and deployments
    within a Foundry project.
    """

    def __init__(self, endpoint: str, credential: TokenCredential) -> None:
        """Initialize the project client service.

        Args:
            endpoint: The project endpoint URL.
            credential: Azure credential for authentication.
        """
        self._endpoint = endpoint
        self._credential = credential
        self._client: AIProjectClient | None = None

    @property
    def client(self) -> AIProjectClient:
        """Get or create the AIProjectClient instance.

        Returns:
            Configured AIProjectClient.
        """
        if self._client is None:
            self._client = AIProjectClient(
                endpoint=self._endpoint,
                credential=self._credential,
            )
        return self._client

    def list_agents(self) -> list[Agent]:
        """List all agents in the project.

        Returns:
            List of agents.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            agents: list[Agent] = []

            # The agents property provides access to agent operations
            agent_list = self.client.agents.list()

            for agent_data in agent_list:
                # Parse created_at timestamp if available
                created_at = None
                if hasattr(agent_data, "created_at") and agent_data.created_at:
                    if isinstance(agent_data.created_at, datetime):
                        created_at = agent_data.created_at
                    elif isinstance(agent_data.created_at, int):
                        created_at = datetime.fromtimestamp(agent_data.created_at)

                agents.append(
                    Agent(
                        id=getattr(agent_data, "id", "") or "",
                        name=getattr(agent_data, "name", "") or "",
                        agent_type="prompt",  # Default type
                        created_at=created_at,
                        instructions=getattr(agent_data, "instructions", None),
                        model=getattr(agent_data, "model", None),
                    )
                )

            return agents
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            raise NetworkError(f"Failed to list agents: {e}") from e

    def list_deployments(self) -> list[Deployment]:
        """List model deployments in the project.

        Returns:
            List of deployments.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            deployments: list[Deployment] = []

            # Get deployments from the inference client
            # Note: The exact API depends on SDK version
            conn_list = self.client.connections.list()

            for conn in conn_list:
                # Filter for model deployments
                conn_type = getattr(conn, "connection_type", "")
                if "azure_open_ai" in str(conn_type).lower():
                    deployments.append(
                        Deployment(
                            name=getattr(conn, "name", "") or "",
                            model=getattr(conn, "name", "") or "",
                            version="",
                            status="Ready",
                        )
                    )

            return deployments
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            raise NetworkError(f"Failed to list deployments: {e}") from e
        except Exception:
            # Return empty list if deployments API is not available
            return []

    def delete_agent(self, agent_id: str) -> None:
        """Delete an agent.

        Args:
            agent_id: The agent ID to delete.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            self.client.agents.delete(agent_id)
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            raise NetworkError(f"Failed to delete agent: {e}") from e
