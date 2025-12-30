"""Project client service for Azure AI Projects SDK operations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    CodeInterpreterTool,
    FileSearchTool,
    MCPTool,
    PromptAgentDefinition,
)
from azure.core.credentials import TokenCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

from anvil.services.exceptions import NetworkError, NotAuthenticated


@dataclass
class ToolConfig:
    """Detailed tool configuration."""

    type: str  # "code_interpreter", "file_search", "mcp", etc.
    display_name: str  # Formatted name for display

    # MCP-specific fields
    server_label: str | None = None
    server_url: str | None = None
    require_approval: str | None = None  # "always", "never", or selective
    project_connection_id: str | None = None

    # FileSearch-specific
    vector_store_ids: list[str] | None = None

    # CodeInterpreter-specific
    file_ids: list[str] | None = None


@dataclass
class Agent:
    """Agent information."""

    id: str
    name: str
    version: str
    agent_type: str
    created_at: datetime | None
    description: str | None
    model: str | None
    instructions: str | None
    tools: list[str]  # Tool type names (for backward compatibility)
    knowledge: list[str]
    memory_enabled: bool
    guardrails: list[str]

    # New detailed fields
    temperature: float | None = None
    top_p: float | None = None
    requires_approval: bool = False  # Whether ANY tool requires approval
    tool_configs: list[ToolConfig] | None = None  # Full tool configurations
    full_metadata: dict[str, str] | None = None  # All custom metadata

    # Publishing info (populated separately via ARM API)
    is_published: bool = False
    published_url: str | None = None
    published_protocols: list[str] | None = None


@dataclass
class Deployment:
    """Model deployment information."""

    name: str
    model_name: str
    model_version: str
    model_publisher: str
    deployment_type: str  # From sku.name (e.g., "Global Standard")
    capacity: int
    capabilities: list[str]  # e.g., ["chat_completion", "embeddings"]


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

    def _parse_created_at(self, value: datetime | int | None) -> datetime | None:
        """Parse created_at timestamp from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, int):
            return datetime.fromtimestamp(value)
        return None

    def _extract_tools(self, agent_data: object) -> list[str]:
        """Extract tool type names from agent tools."""
        tools: list[str] = []
        agent_tools = getattr(agent_data, "tools", None)
        if not agent_tools:
            return tools

        for tool in agent_tools:
            # Tool type is the discriminator - could be string or enum
            tool_type = getattr(tool, "type", None)
            if tool_type:
                # Convert enum to string if needed, format nicely
                type_str = str(tool_type)
                # Handle enum values like "ToolType.CODE_INTERPRETER"
                if "." in type_str:
                    type_str = type_str.split(".")[-1]
                # Convert snake_case to Title Case
                type_str = type_str.replace("_", " ").title()
                tools.append(type_str)
        return tools

    def _extract_knowledge(self, agent_data: object) -> list[str]:
        """Extract knowledge base IDs from tool resources."""
        knowledge: list[str] = []
        tool_resources = getattr(agent_data, "tool_resources", None)
        if not tool_resources:
            return knowledge

        # Check file_search vector stores
        file_search = getattr(tool_resources, "file_search", None)
        if file_search:
            vector_store_ids = getattr(file_search, "vector_store_ids", None)
            if vector_store_ids:
                knowledge.extend(vector_store_ids)

        # Check code_interpreter files
        code_interpreter = getattr(tool_resources, "code_interpreter", None)
        if code_interpreter:
            file_ids = getattr(code_interpreter, "file_ids", None)
            if file_ids:
                knowledge.extend(file_ids)

        return knowledge

    def _extract_metadata_field(
        self, agent_data: object, key: str, default: object = None
    ) -> object:
        """Extract a field from agent metadata."""
        metadata = getattr(agent_data, "metadata", None)
        if metadata and isinstance(metadata, dict):
            return metadata.get(key, default)
        return default

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
                # The API returns data nested under versions.latest.definition
                # Get the versions object
                versions = getattr(agent_data, "versions", None)
                latest_version: Any = None
                definition: Any = None

                if versions:
                    # versions can be dict-like or have 'latest' attribute
                    if hasattr(versions, "get"):
                        latest_version = versions.get("latest")
                    elif hasattr(versions, "latest"):
                        latest_version = versions.latest

                if latest_version:
                    if hasattr(latest_version, "get"):
                        definition = latest_version.get("definition", {})
                    elif hasattr(latest_version, "definition"):
                        definition = latest_version.definition

                # Extract version info using safe dict/attr access
                version = "-"
                created_at_raw = None
                description = None
                if latest_version:
                    if hasattr(latest_version, "get"):
                        version = str(latest_version.get("version", "-"))
                        created_at_raw = latest_version.get("created_at")
                        description = latest_version.get("description") or None
                    else:
                        version = str(getattr(latest_version, "version", "-"))
                        created_at_raw = getattr(latest_version, "created_at", None)
                        description = getattr(latest_version, "description", None)

                # Extract from definition
                agent_type = "Assistant"
                model = None
                instructions = None
                tools_raw: list[Any] = []
                temperature: float | None = None
                top_p: float | None = None

                if definition:
                    if hasattr(definition, "get"):
                        agent_type = str(definition.get("kind", "Assistant")).title()
                        model = definition.get("model")
                        instructions = definition.get("instructions")
                        tools_raw = definition.get("tools", []) or []
                        temperature = definition.get("temperature")
                        top_p = definition.get("top_p")
                    else:
                        agent_type = str(getattr(definition, "kind", "Assistant")).title()
                        model = getattr(definition, "model", None)
                        instructions = getattr(definition, "instructions", None)
                        tools_raw = getattr(definition, "tools", []) or []
                        temperature = getattr(definition, "temperature", None)
                        top_p = getattr(definition, "top_p", None)

                # Extract tools from definition - both simple list and full configs
                tools: list[str] = []
                tool_configs: list[ToolConfig] = []
                requires_approval = False

                if tools_raw:
                    for tool in tools_raw:
                        # Get tool type
                        if hasattr(tool, "get"):
                            tool_type = tool.get("type", "")
                            server_label = tool.get("server_label")
                            server_url = tool.get("server_url")
                            require_approval = tool.get("require_approval")
                            project_connection_id = tool.get("project_connection_id")
                        else:
                            tool_type = getattr(tool, "type", "")
                            server_label = getattr(tool, "server_label", None)
                            server_url = getattr(tool, "server_url", None)
                            require_approval = getattr(tool, "require_approval", None)
                            project_connection_id = getattr(tool, "project_connection_id", None)

                        if tool_type:
                            # Format tool type nicely for display
                            display_name = str(tool_type).replace("_", " ").title()
                            tools.append(display_name)

                            # Build full ToolConfig
                            tool_config = ToolConfig(
                                type=str(tool_type),
                                display_name=display_name,
                                server_label=server_label,
                                server_url=server_url,
                                require_approval=require_approval,
                                project_connection_id=project_connection_id,
                            )
                            tool_configs.append(tool_config)

                            # Check if any tool requires approval
                            if require_approval == "always":
                                requires_approval = True

                # Extract knowledge (tool resources with file_search or similar)
                knowledge: list[str] = []
                for tool in tools_raw or []:
                    if hasattr(tool, "get"):
                        server_label = tool.get("server_label", "")
                        if server_label and "kb" in server_label.lower():
                            knowledge.append(server_label)
                    else:
                        server_label = getattr(tool, "server_label", "")
                        if server_label and "kb" in server_label.lower():
                            knowledge.append(server_label)

                # Extract metadata for memory/guardrails
                metadata: dict[str, Any] = {}
                if latest_version:
                    if hasattr(latest_version, "get"):
                        metadata = latest_version.get("metadata", {}) or {}
                    else:
                        metadata = getattr(latest_version, "metadata", {}) or {}
                memory_enabled = bool(
                    metadata.get("memory_enabled", False) if isinstance(metadata, dict) else False
                )

                guardrails: list[str] = []
                if isinstance(metadata, dict):
                    if metadata.get("content_filter"):
                        guardrails.append("Content Filter")
                    if metadata.get("grounding"):
                        guardrails.append("Grounding")

                # Convert metadata to string dict for full_metadata
                full_metadata: dict[str, str] | None = None
                if metadata and isinstance(metadata, dict):
                    full_metadata = {str(k): str(v) for k, v in metadata.items()}

                agents.append(
                    Agent(
                        id=getattr(agent_data, "id", "") or "",
                        name=getattr(agent_data, "name", "") or "",
                        version=version,
                        agent_type=agent_type,
                        created_at=self._parse_created_at(created_at_raw),
                        description=description if description else None,
                        model=model,
                        instructions=instructions,
                        tools=tools,
                        knowledge=knowledge,
                        memory_enabled=memory_enabled,
                        guardrails=guardrails,
                        temperature=temperature,
                        top_p=top_p,
                        requires_approval=requires_approval,
                        tool_configs=tool_configs if tool_configs else None,
                        full_metadata=full_metadata,
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
            List of deployments sorted by name.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            deployments: list[Deployment] = []

            # Get deployments from the deployments API
            deployment_list = self.client.deployments.list()

            for dep in deployment_list:
                # Extract sku information
                sku = getattr(dep, "sku", None)
                sku_name = ""
                capacity = 0
                if sku:
                    if hasattr(sku, "get"):
                        sku_name = sku.get("name", "")
                        capacity = sku.get("capacity", 0)
                    else:
                        sku_name = getattr(sku, "name", "")
                        capacity = getattr(sku, "capacity", 0)

                # Format sku name nicely (e.g., "GlobalStandard" -> "Global Standard")
                deployment_type = ""
                if sku_name:
                    # Insert space before capital letters
                    deployment_type = "".join(
                        " " + c if c.isupper() and i > 0 else c for i, c in enumerate(sku_name)
                    ).strip()

                # Extract capabilities
                capabilities_dict = getattr(dep, "capabilities", {}) or {}
                capabilities = [
                    k.replace("_", " ").title()
                    for k, v in capabilities_dict.items()
                    if v == "true" or v is True
                ]

                deployments.append(
                    Deployment(
                        name=getattr(dep, "name", "") or "",
                        model_name=getattr(dep, "model_name", "") or "",
                        model_version=getattr(dep, "model_version", "") or "",
                        model_publisher=getattr(dep, "model_publisher", "") or "",
                        deployment_type=deployment_type,
                        capacity=capacity,
                        capabilities=capabilities,
                    )
                )

            # Sort by name
            deployments.sort(key=lambda d: d.name.lower())
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

    def get_chat_completion_models(self) -> list[Deployment]:
        """Get deployments suitable for agents (chat completion capable).

        Filters out embedding models and other non-chat models.

        Returns:
            List of deployments that support chat completion.
        """
        all_deployments = self.list_deployments()
        return [d for d in all_deployments if "Chat Completion" in d.capabilities]

    def _build_tools_from_configs(
        self, tool_configs: list[ToolConfig]
    ) -> list[CodeInterpreterTool | FileSearchTool | MCPTool]:
        """Build SDK tool objects from ToolConfig list."""
        tools: list[CodeInterpreterTool | FileSearchTool | MCPTool] = []
        for config in tool_configs:
            if config.type == "code_interpreter":
                # CodeInterpreterTool requires container parameter
                tools.append(CodeInterpreterTool(container="auto"))
            elif config.type == "file_search":
                # FileSearchTool requires vector_store_ids
                vs_ids = config.vector_store_ids or []
                if vs_ids:
                    tools.append(FileSearchTool(vector_store_ids=vs_ids))
            elif config.type == "mcp":
                # MCPTool requires keyword arguments
                # require_approval must be "always" or "never"
                require_approval_raw = config.require_approval or "always"
                require_approval_val: str = "never" if require_approval_raw == "never" else "always"
                mcp_tool = MCPTool(  # type: ignore[call-overload]
                    server_label=config.server_label or "",
                    server_url=config.server_url or "",
                    require_approval=require_approval_val,
                    project_connection_id=config.project_connection_id,
                )
                tools.append(mcp_tool)
        return tools

    def create_agent(
        self,
        name: str,
        model: str,
        instructions: str,
        temperature: float | None = None,
        top_p: float | None = None,
        tool_configs: list[ToolConfig] | None = None,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Agent:
        """Create a new agent.

        Args:
            name: Agent name (required).
            model: Model deployment name (required).
            instructions: System instructions (required).
            temperature: Sampling temperature (0-2).
            top_p: Nucleus sampling parameter (0-1).
            tool_configs: List of tool configurations.
            description: Optional agent description.
            metadata: Optional custom metadata.

        Returns:
            The created Agent.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            # Build tools from configs
            tools = self._build_tools_from_configs(tool_configs or [])

            # Build definition (PromptAgentDefinition uses keyword args only)
            definition = PromptAgentDefinition(
                model=model,
                instructions=instructions,
                temperature=temperature,
                top_p=top_p,
                tools=tools if tools else None,  # type: ignore[arg-type]
            )

            # Create the agent
            self.client.agents.create(
                name=name,
                definition=definition,
                description=description,
                metadata=metadata,
            )

            # Refresh and return the created agent
            agents = self.list_agents()
            for agent in agents:
                if agent.name == name:
                    return agent

            # Fallback if not found (shouldn't happen)
            raise NetworkError(f"Agent '{name}' created but not found in list")
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            raise NetworkError(f"Failed to create agent: {e}") from e

    def update_agent(
        self,
        agent_name: str,
        model: str,
        instructions: str,
        temperature: float | None = None,
        top_p: float | None = None,
        tool_configs: list[ToolConfig] | None = None,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Agent:
        """Update an existing agent.

        Args:
            agent_name: Agent name to update.
            model: Model deployment name.
            instructions: System instructions.
            temperature: Sampling temperature (0-2).
            top_p: Nucleus sampling parameter (0-1).
            tool_configs: List of tool configurations.
            description: Optional agent description.
            metadata: Optional custom metadata.

        Returns:
            The updated Agent.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            # Build tools from configs
            tools = self._build_tools_from_configs(tool_configs or [])

            # Build definition (PromptAgentDefinition uses keyword args only)
            definition = PromptAgentDefinition(
                model=model,
                instructions=instructions,
                temperature=temperature,
                top_p=top_p,
                tools=tools if tools else None,  # type: ignore[arg-type]
            )

            # Update the agent
            self.client.agents.update(
                agent_name=agent_name,
                definition=definition,
                description=description,
                metadata=metadata,
            )

            # Refresh and return the updated agent
            agents = self.list_agents()
            for agent in agents:
                if agent.name == agent_name:
                    return agent

            # Fallback if not found (shouldn't happen)
            raise NetworkError(f"Agent '{agent_name}' updated but not found in list")
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            raise NetworkError(f"Failed to update agent: {e}") from e
