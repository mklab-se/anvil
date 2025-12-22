"""Tests for ProjectClientService - especially API response parsing."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from anvil.services.project_client import Agent, ProjectClientService


class TestListAgentsParsing:
    """Tests for parsing the Azure AI SDK agent response structure."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock AIProjectClient."""
        with patch("anvil.services.project_client.AIProjectClient") as mock:
            yield mock

    @pytest.fixture
    def service(self, mock_client):
        """Create a ProjectClientService with mocked client."""
        mock_credential = MagicMock()
        return ProjectClientService(
            endpoint="https://test.endpoint",
            credential=mock_credential,
        )

    def _create_mock_agent(
        self,
        agent_id: str,
        name: str,
        version: str = "1",
        kind: str = "prompt",
        model: str = "gpt-4o",
        instructions: str | None = "Test instructions",
        description: str = "",
        created_at: int = 1734500000,
        tools: list | None = None,
        metadata: dict | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> MagicMock:
        """Create a mock agent with the real Azure SDK structure.

        The real structure is:
        {
            "object": "agent",
            "id": "agent-id",
            "name": "agent-name",
            "versions": {
                "latest": {
                    "version": "1",
                    "created_at": 1734500000,
                    "description": "",
                    "metadata": {},
                    "definition": {
                        "kind": "prompt",
                        "model": "gpt-4o",
                        "instructions": "...",
                        "temperature": 1,
                        "top_p": 1,
                        "tools": [...]
                    }
                }
            }
        }
        """
        mock_agent = MagicMock()
        mock_agent.id = agent_id
        mock_agent.name = name

        # Create the nested versions structure (dict-like)
        definition = {
            "kind": kind,
            "model": model,
            "instructions": instructions,
            "tools": tools or [],
        }

        # Add optional temperature and top_p if provided
        if temperature is not None:
            definition["temperature"] = temperature
        if top_p is not None:
            definition["top_p"] = top_p

        mock_agent.versions = {
            "latest": {
                "version": version,
                "created_at": created_at,
                "description": description,
                "metadata": metadata or {},
                "definition": definition,
            }
        }

        return mock_agent

    def test_parses_basic_agent_fields(self, service, mock_client):
        """Test that basic agent fields are parsed correctly."""
        mock_agent = self._create_mock_agent(
            agent_id="test-agent",
            name="Test Agent",
            version="3",
            kind="prompt",
            model="gpt-4o-mini",
            created_at=1734567890,
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert len(agents) == 1
        agent = agents[0]
        assert agent.id == "test-agent"
        assert agent.name == "Test Agent"
        assert agent.version == "3"
        assert agent.agent_type == "Prompt"
        assert agent.model == "gpt-4o-mini"

    def test_parses_created_at_unix_timestamp(self, service, mock_client):
        """Test that Unix timestamp is converted to datetime."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            created_at=1734567890,  # 2024-12-18 something
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].created_at is not None
        assert isinstance(agents[0].created_at, datetime)

    def test_parses_instructions(self, service, mock_client):
        """Test that instructions are extracted from definition."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            instructions="You are a helpful assistant that answers questions.",
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].instructions == "You are a helpful assistant that answers questions."

    def test_parses_tools_from_definition(self, service, mock_client):
        """Test that tools are extracted and formatted correctly."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[
                {"type": "code_interpreter"},
                {"type": "file_search"},
                {"type": "mcp", "server_label": "kb_docs"},
            ],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert "Code Interpreter" in agents[0].tools
        assert "File Search" in agents[0].tools
        assert "Mcp" in agents[0].tools

    def test_extracts_knowledge_from_mcp_tools(self, service, mock_client):
        """Test that knowledge base IDs are extracted from MCP tools."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[
                {"type": "mcp", "server_label": "kb_my_knowledge_base"},
                {"type": "mcp", "server_label": "kb_docs_v2"},
            ],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert "kb_my_knowledge_base" in agents[0].knowledge
        assert "kb_docs_v2" in agents[0].knowledge

    def test_handles_missing_instructions(self, service, mock_client):
        """Test graceful handling when instructions are None."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            instructions=None,
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].instructions is None

    def test_handles_missing_tools(self, service, mock_client):
        """Test graceful handling when tools list is empty."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].tools == []

    def test_handles_empty_description(self, service, mock_client):
        """Test that empty description becomes None."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            description="",
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        # Empty string should be converted to None
        assert agents[0].description is None

    def test_handles_multiple_agents(self, service, mock_client):
        """Test parsing multiple agents."""
        mock_agents = [
            self._create_mock_agent("agent-1", "First Agent", model="gpt-4o"),
            self._create_mock_agent("agent-2", "Second Agent", model="gpt-4o-mini"),
            self._create_mock_agent("agent-3", "Third Agent", model="gpt-4.1"),
        ]

        mock_client.return_value.agents.list.return_value = mock_agents

        agents = service.list_agents()

        assert len(agents) == 3
        assert agents[0].name == "First Agent"
        assert agents[1].name == "Second Agent"
        assert agents[2].name == "Third Agent"

    def test_handles_empty_agent_list(self, service, mock_client):
        """Test handling empty agent list."""
        mock_client.return_value.agents.list.return_value = []

        agents = service.list_agents()

        assert agents == []

    def test_extracts_metadata_memory_enabled(self, service, mock_client):
        """Test extraction of memory_enabled from metadata."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            metadata={"memory_enabled": True},
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].memory_enabled is True

    def test_memory_disabled_by_default(self, service, mock_client):
        """Test that memory is disabled when not in metadata."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            metadata={},
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].memory_enabled is False

    def test_parses_temperature_and_top_p(self, service, mock_client):
        """Test that temperature and top_p are parsed from definition."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            temperature=0.7,
            top_p=0.95,
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].temperature == 0.7
        assert agents[0].top_p == 0.95

    def test_parses_mcp_tool_approval_always(self, service, mock_client):
        """Test parsing MCP tool with require_approval=always."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[
                {
                    "type": "mcp",
                    "server_label": "kb_docs_test",
                    "server_url": "https://test.search.windows.net/kb",
                    "require_approval": "always",
                    "project_connection_id": "kb-docs-test",
                }
            ],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()
        agent = agents[0]

        assert agent.requires_approval is True
        assert agent.tool_configs is not None
        assert len(agent.tool_configs) == 1
        assert agent.tool_configs[0].type == "mcp"
        assert agent.tool_configs[0].require_approval == "always"
        assert agent.tool_configs[0].server_label == "kb_docs_test"

    def test_parses_mcp_tool_approval_never(self, service, mock_client):
        """Test parsing MCP tool with require_approval=never."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[
                {
                    "type": "mcp",
                    "server_label": "kb_manuals",
                    "server_url": "https://test.search.windows.net/kb",
                    "require_approval": "never",
                    "project_connection_id": "kb-manuals",
                }
            ],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()
        agent = agents[0]

        assert agent.requires_approval is False
        assert agent.tool_configs is not None
        assert agent.tool_configs[0].require_approval == "never"

    def test_requires_approval_true_when_any_tool_requires(self, service, mock_client):
        """Test that requires_approval is True when any tool requires approval."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[
                {"type": "code_interpreter"},
                {
                    "type": "mcp",
                    "server_label": "kb_docs",
                    "require_approval": "always",
                },
            ],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].requires_approval is True

    def test_requires_approval_false_when_all_never(self, service, mock_client):
        """Test that requires_approval is False when no tools require approval."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[
                {"type": "code_interpreter"},
                {
                    "type": "mcp",
                    "server_label": "kb_docs",
                    "require_approval": "never",
                },
            ],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()

        assert agents[0].requires_approval is False

    def test_parses_tool_configs_with_details(self, service, mock_client):
        """Test that tool_configs contain full tool details."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            tools=[
                {"type": "code_interpreter"},
                {
                    "type": "mcp",
                    "server_label": "kb_test_kb",
                    "server_url": "https://test.search.windows.net/kb",
                    "require_approval": "always",
                    "project_connection_id": "kb-test",
                },
            ],
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()
        agent = agents[0]

        assert agent.tool_configs is not None
        assert len(agent.tool_configs) == 2

        # First tool should be code interpreter
        assert agent.tool_configs[0].type == "code_interpreter"
        assert agent.tool_configs[0].display_name == "Code Interpreter"

        # Second tool should be MCP with full details
        mcp_tool = agent.tool_configs[1]
        assert mcp_tool.type == "mcp"
        assert mcp_tool.server_label == "kb_test_kb"
        assert mcp_tool.server_url == "https://test.search.windows.net/kb"
        assert mcp_tool.project_connection_id == "kb-test"

    def test_parses_full_metadata(self, service, mock_client):
        """Test that full_metadata contains all metadata keys."""
        mock_agent = self._create_mock_agent(
            agent_id="test",
            name="test",
            metadata={"custom_key": "custom_value", "another_key": "another_value"},
        )

        mock_client.return_value.agents.list.return_value = [mock_agent]

        agents = service.list_agents()
        agent = agents[0]

        assert agent.full_metadata is not None
        assert agent.full_metadata["custom_key"] == "custom_value"
        assert agent.full_metadata["another_key"] == "another_value"


class TestAgentDataclass:
    """Tests for the Agent dataclass."""

    def test_agent_has_all_required_fields(self):
        """Test that Agent dataclass has all required fields."""
        agent = Agent(
            id="test-id",
            name="Test Agent",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description="Test description",
            model="gpt-4o",
            instructions="Test instructions",
            tools=["Code Interpreter"],
            knowledge=["kb_test"],
            memory_enabled=True,
            guardrails=["Content Filter"],
        )

        assert agent.id == "test-id"
        assert agent.name == "Test Agent"
        assert agent.version == "1"
        assert agent.agent_type == "Prompt"
        assert agent.model == "gpt-4o"
        assert agent.instructions == "Test instructions"
        assert agent.tools == ["Code Interpreter"]
        assert agent.knowledge == ["kb_test"]
        assert agent.memory_enabled is True
        assert agent.guardrails == ["Content Filter"]


class TestListDeploymentsParsing:
    """Tests for parsing the Azure AI SDK deployment response structure."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock AIProjectClient."""
        with patch("anvil.services.project_client.AIProjectClient") as mock:
            yield mock

    @pytest.fixture
    def service(self, mock_client):
        """Create a ProjectClientService with mocked client."""
        mock_credential = MagicMock()
        return ProjectClientService(
            endpoint="https://test.endpoint",
            credential=mock_credential,
        )

    def _create_mock_deployment(
        self,
        name: str,
        model_name: str,
        model_version: str = "1",
        model_publisher: str = "OpenAI",
        sku_name: str = "GlobalStandard",
        capacity: int = 100,
        capabilities: dict | None = None,
    ) -> MagicMock:
        """Create a mock deployment with the real Azure SDK structure."""
        mock_deployment = MagicMock()
        mock_deployment.name = name
        mock_deployment.model_name = model_name
        mock_deployment.model_version = model_version
        mock_deployment.model_publisher = model_publisher
        mock_deployment.sku = {"name": sku_name, "capacity": capacity}
        mock_deployment.capabilities = capabilities or {}
        return mock_deployment

    def test_parses_basic_deployment_fields(self, service, mock_client):
        """Test that basic deployment fields are parsed correctly."""
        mock_dep = self._create_mock_deployment(
            name="gpt-4o",
            model_name="gpt-4o",
            model_version="2024-08-06",
            model_publisher="OpenAI",
        )

        mock_client.return_value.deployments.list.return_value = [mock_dep]

        deployments = service.list_deployments()

        assert len(deployments) == 1
        dep = deployments[0]
        assert dep.name == "gpt-4o"
        assert dep.model_name == "gpt-4o"
        assert dep.model_version == "2024-08-06"
        assert dep.model_publisher == "OpenAI"

    def test_parses_sku_into_deployment_type(self, service, mock_client):
        """Test that sku.name is parsed into deployment_type with formatting."""
        mock_dep = self._create_mock_deployment(
            name="test",
            model_name="test",
            sku_name="GlobalStandard",
            capacity=150,
        )

        mock_client.return_value.deployments.list.return_value = [mock_dep]

        deployments = service.list_deployments()

        assert deployments[0].deployment_type == "Global Standard"
        assert deployments[0].capacity == 150

    def test_parses_capabilities(self, service, mock_client):
        """Test that capabilities are parsed correctly."""
        mock_dep = self._create_mock_deployment(
            name="test",
            model_name="test",
            capabilities={"chat_completion": "true", "embeddings": "true"},
        )

        mock_client.return_value.deployments.list.return_value = [mock_dep]

        deployments = service.list_deployments()

        assert "Chat Completion" in deployments[0].capabilities
        assert "Embeddings" in deployments[0].capabilities

    def test_handles_empty_capabilities(self, service, mock_client):
        """Test handling of empty capabilities."""
        mock_dep = self._create_mock_deployment(
            name="test",
            model_name="test",
            capabilities={},
        )

        mock_client.return_value.deployments.list.return_value = [mock_dep]

        deployments = service.list_deployments()

        assert deployments[0].capabilities == []

    def test_handles_multiple_deployments(self, service, mock_client):
        """Test parsing multiple deployments."""
        mock_deps = [
            self._create_mock_deployment("gpt-4o", "gpt-4o"),
            self._create_mock_deployment("gpt-4o-mini", "gpt-4o-mini"),
            self._create_mock_deployment("text-embedding-3-small", "text-embedding-3-small"),
        ]

        mock_client.return_value.deployments.list.return_value = mock_deps

        deployments = service.list_deployments()

        assert len(deployments) == 3

    def test_sorts_deployments_by_name(self, service, mock_client):
        """Test that deployments are sorted by name."""
        mock_deps = [
            self._create_mock_deployment("zebra-model", "zebra"),
            self._create_mock_deployment("alpha-model", "alpha"),
            self._create_mock_deployment("beta-model", "beta"),
        ]

        mock_client.return_value.deployments.list.return_value = mock_deps

        deployments = service.list_deployments()

        assert deployments[0].name == "alpha-model"
        assert deployments[1].name == "beta-model"
        assert deployments[2].name == "zebra-model"

    def test_handles_empty_deployment_list(self, service, mock_client):
        """Test handling empty deployment list."""
        mock_client.return_value.deployments.list.return_value = []

        deployments = service.list_deployments()

        assert deployments == []


class TestDeploymentDataclass:
    """Tests for the Deployment dataclass."""

    def test_deployment_has_all_required_fields(self):
        """Test that Deployment dataclass has all required fields."""
        from anvil.services.project_client import Deployment

        dep = Deployment(
            name="gpt-4o",
            model_name="gpt-4o",
            model_version="2024-08-06",
            model_publisher="OpenAI",
            deployment_type="Global Standard",
            capacity=100,
            capabilities=["Chat Completion"],
        )

        assert dep.name == "gpt-4o"
        assert dep.model_name == "gpt-4o"
        assert dep.model_version == "2024-08-06"
        assert dep.model_publisher == "OpenAI"
        assert dep.deployment_type == "Global Standard"
        assert dep.capacity == 100
        assert dep.capabilities == ["Chat Completion"]


class TestParseCreatedAt:
    """Tests for the _parse_created_at helper method."""

    @pytest.fixture
    def service(self):
        """Create a ProjectClientService for testing helpers."""
        mock_credential = MagicMock()
        with patch("anvil.services.project_client.AIProjectClient"):
            return ProjectClientService(
                endpoint="https://test.endpoint",
                credential=mock_credential,
            )

    def test_parses_unix_timestamp(self, service):
        """Test parsing Unix timestamp integer."""
        result = service._parse_created_at(1734567890)
        assert isinstance(result, datetime)

    def test_passes_through_datetime(self, service):
        """Test that datetime objects are returned as-is."""
        dt = datetime(2024, 12, 18, 10, 30, 0)
        result = service._parse_created_at(dt)
        assert result == dt

    def test_returns_none_for_none(self, service):
        """Test that None input returns None."""
        result = service._parse_created_at(None)
        assert result is None
