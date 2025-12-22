"""Tests for Anvil screens."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from anvil.app import AnvilApp
from anvil.config import AppConfig, FoundrySelection
from anvil.screens.home import HomeScreen
from anvil.services.auth import AuthResult, AuthStatus
from anvil.services.project_client import Agent, Deployment


@pytest.fixture
def mock_auth_and_config():
    """Mock both auth and config for testing home screen."""
    selection = FoundrySelection(
        subscription_id="test-sub-id",
        subscription_name="Test Subscription",
        resource_group="test-rg",
        account_name="test-account",
        project_name="test-project",
        project_endpoint="https://test.endpoint",
        selected_at=datetime.now(),
    )
    config = AppConfig(last_selection=selection, auto_connect_last=True)

    with (
        patch("anvil.app.AuthService") as mock_auth_cls,
        patch("anvil.app.ConfigManager") as mock_config_cls,
    ):
        mock_auth = mock_auth_cls.return_value
        mock_auth.check_auth_status.return_value = AuthResult(status=AuthStatus.AUTHENTICATED)
        mock_auth.is_authenticated.return_value = True
        # Return None for credential to prevent real API calls in tests
        mock_auth.get_credential.return_value = None

        mock_config = mock_config_cls.return_value
        mock_config.load.return_value = config
        mock_config.get_last_subscription_id.return_value = selection.subscription_id
        mock_config.get_last_account_name.return_value = selection.account_name
        mock_config.get_last_project_name.return_value = selection.project_name

        yield {"auth": mock_auth, "config": mock_config, "selection": selection}


async def test_home_screen_renders(mock_auth_and_config) -> None:
    """Test that the home screen renders correctly."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        # Skip splash screen
        await pilot.press("enter")
        assert isinstance(app.screen, HomeScreen)

        # Check main container exists
        main_container = app.screen.query_one("#main-container")
        assert main_container is not None


async def test_home_screen_has_sidebar(mock_auth_and_config) -> None:
    """Test that the home screen has a sidebar with navigation."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        # Skip splash screen
        await pilot.press("enter")

        from anvil.widgets.sidebar import Sidebar

        sidebar = app.screen.query_one("#sidebar", Sidebar)
        assert sidebar is not None

        # Check sidebar has resource items
        assert len(sidebar._items) > 0


async def test_home_screen_has_resource_table(mock_auth_and_config) -> None:
    """Test that the home screen has a resource table."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        # Skip splash screen
        await pilot.press("enter")

        from textual.widgets import DataTable

        table = app.screen.query_one("#resource-table", DataTable)
        assert table is not None

        # Check table has columns and rows (placeholder data)
        assert table.row_count > 0


async def test_agents_table_has_correct_columns(mock_auth_and_config) -> None:
    """Test that the agents table has the correct columns."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")  # Skip splash

        from textual.widgets import DataTable

        table = app.screen.query_one("#resource-table", DataTable)

        # Get column labels
        columns = [col.label.plain for col in table.columns.values()]
        assert columns == ["Name", "Version", "Type", "Created", "Description"]


async def test_agents_table_rows_have_data(mock_auth_and_config) -> None:
    """Test that agent table rows have actual data in all columns."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")  # Skip splash

        from textual.widgets import DataTable

        table = app.screen.query_one("#resource-table", DataTable)
        assert table.row_count > 0

        # Get first row data
        first_row_key = next(iter(table.rows.keys()))
        row_data = table.get_row(first_row_key)

        # All columns should have data (not empty strings)
        name, version, agent_type, created, description = row_data
        assert name, "Name should not be empty"
        assert version, "Version should not be empty"
        assert agent_type, "Type should not be empty"
        assert created, "Created should not be empty"
        assert description, "Description should not be empty"


async def test_agents_stored_in_screen(mock_auth_and_config) -> None:
    """Test that Agent objects are stored in the screen for lookup."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")  # Skip splash

        home_screen = app.screen
        assert hasattr(home_screen, "_agents")
        assert len(home_screen._agents) > 0

        # Verify agents have required fields
        agent = home_screen._agents[0]
        assert agent.id, "Agent should have an ID"
        assert agent.name, "Agent should have a name"
        assert agent.model, "Agent should have a model"


async def test_sidebar_preview_shows_agent_details(mock_auth_and_config) -> None:
    """Test that sidebar shows agent details when row is highlighted."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")  # Skip splash

        from textual.widgets import DataTable

        # Focus the table and trigger row highlight
        table = app.screen.query_one("#resource-table", DataTable)
        table.focus()
        await pilot.pause()

        # Move cursor to ensure row is highlighted (triggers on_data_table_row_highlighted)
        await pilot.press("down")
        await pilot.press("up")
        await pilot.pause()

        # Check that the preview panel is visible
        preview_panel = app.screen.query_one("#preview-panel")
        assert "visible" in preview_panel.classes, "Preview panel should be visible"

        # Verify agent was looked up correctly
        home_screen = app.screen
        assert len(home_screen._agents) > 0, "Should have agents loaded"

        # The first agent should have model set
        first_agent = home_screen._agents[0]
        assert first_agent.model is not None, f"First agent should have model, got: {first_agent}"


async def test_agent_lookup_by_id(mock_auth_and_config) -> None:
    """Test that _get_agent_by_id works correctly."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")  # Skip splash

        home_screen = app.screen

        # Get the first agent
        if home_screen._agents:
            first_agent = home_screen._agents[0]
            # Lookup should return the same agent
            found_agent = home_screen._get_agent_by_id(first_agent.id)
            assert found_agent is not None, "Should find agent by ID"
            assert found_agent.id == first_agent.id
            assert found_agent.name == first_agent.name


class TestViewSwitchingRaceCondition:
    """Tests for race conditions when switching between views quickly."""

    @pytest.fixture
    def home_screen(self):
        """Create a HomeScreen for testing."""
        return HomeScreen()

    @pytest.fixture
    def sample_agents(self):
        """Create sample agents for testing."""
        return [
            Agent(
                id="agent-1",
                name="Test Agent",
                version="1",
                agent_type="Prompt",
                created_at=datetime.now(),
                description="Test",
                model="gpt-4o",
                instructions=None,
                tools=[],
                knowledge=[],
                memory_enabled=False,
                guardrails=[],
            )
        ]

    @pytest.fixture
    def sample_deployments(self):
        """Create sample deployments for testing."""
        return [
            Deployment(
                name="gpt-4o",
                model_name="gpt-4o",
                model_version="2024-08-06",
                model_publisher="OpenAI",
                deployment_type="Global Standard",
                capacity=100,
                capabilities=["Chat Completion"],
            )
        ]

    def test_agents_not_populated_when_on_models_view(self, home_screen, sample_agents):
        """Test that agent data doesn't populate table when user switched to models view.

        This catches the race condition where:
        1. User is on agents view, agents start loading
        2. User switches to models view
        3. Agents finish loading - they should NOT populate the models table
        """
        from textual.worker import Worker, WorkerState

        # Simulate being on models view when agents finish loading
        home_screen._current_resource = "models"
        home_screen._agents = []  # No agents loaded yet

        # Create a mock worker that completed with agent results
        mock_worker = MagicMock(spec=Worker)
        mock_worker.name = "fetch_agents"
        mock_worker.result = sample_agents

        # Create state changed event
        mock_event = MagicMock()
        mock_event.worker = mock_worker
        mock_event.state = WorkerState.SUCCESS

        # Track if _populate_agents_table was called
        populate_called = False
        original_populate = home_screen._populate_agents_table

        def track_populate():
            nonlocal populate_called
            populate_called = True
            original_populate()

        home_screen._populate_agents_table = track_populate

        # Trigger the worker completion handler
        home_screen.on_worker_state_changed(mock_event)

        # Agents data should be stored but table should NOT be populated
        assert home_screen._agents == sample_agents, "Agent data should still be stored"
        assert not populate_called, "Table should NOT be populated when on models view"

    def test_deployments_not_populated_when_on_agents_view(self, home_screen, sample_deployments):
        """Test that deployment data doesn't populate table when user switched to agents view.

        This catches the race condition where:
        1. User is on models view, deployments start loading
        2. User switches to agents view
        3. Deployments finish loading - they should NOT populate the agents table
        """
        from textual.worker import Worker, WorkerState

        # Simulate being on agents view when deployments finish loading
        home_screen._current_resource = "agents"
        home_screen._deployments = []  # No deployments loaded yet

        # Create a mock worker that completed with deployment results
        mock_worker = MagicMock(spec=Worker)
        mock_worker.name = "fetch_deployments"
        mock_worker.result = sample_deployments

        # Create state changed event
        mock_event = MagicMock()
        mock_event.worker = mock_worker
        mock_event.state = WorkerState.SUCCESS

        # Track if _populate_models_table was called
        populate_called = False
        original_populate = home_screen._populate_models_table

        def track_populate():
            nonlocal populate_called
            populate_called = True
            original_populate()

        home_screen._populate_models_table = track_populate

        # Trigger the worker completion handler
        home_screen.on_worker_state_changed(mock_event)

        # Deployment data should be stored but table should NOT be populated
        assert home_screen._deployments == sample_deployments, "Deployment data should still be stored"
        assert not populate_called, "Table should NOT be populated when on agents view"

    def test_agents_populated_when_still_on_agents_view(self, home_screen, sample_agents):
        """Test that agent data DOES populate table when still on agents view."""
        from textual.worker import Worker, WorkerState

        # Simulate still being on agents view when agents finish loading
        home_screen._current_resource = "agents"

        mock_worker = MagicMock(spec=Worker)
        mock_worker.name = "fetch_agents"
        mock_worker.result = sample_agents

        mock_event = MagicMock()
        mock_event.worker = mock_worker
        mock_event.state = WorkerState.SUCCESS

        populate_called = False
        original_populate = home_screen._populate_agents_table

        def track_populate():
            nonlocal populate_called
            populate_called = True
            # Don't call original - it needs a mounted widget

        home_screen._populate_agents_table = track_populate

        home_screen.on_worker_state_changed(mock_event)

        assert home_screen._agents == sample_agents
        assert populate_called, "Table SHOULD be populated when still on agents view"


class TestFormatAgentPreview:
    """Tests for the _format_agent_preview method."""

    @pytest.fixture
    def home_screen(self):
        """Create a HomeScreen instance for testing."""
        return HomeScreen()

    def test_formats_model(self, home_screen):
        """Test that model is displayed correctly."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o-mini",
            instructions=None,
            tools=[],
            knowledge=[],
            memory_enabled=False,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Model:" in result
        assert "gpt-4o-mini" in result

    def test_formats_model_not_set(self, home_screen):
        """Test display when model is None."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model=None,
            instructions=None,
            tools=[],
            knowledge=[],
            memory_enabled=False,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Not set" in result

    def test_formats_instructions_truncated(self, home_screen):
        """Test that long instructions are truncated."""
        long_instructions = "A" * 200  # 200 characters
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o",
            instructions=long_instructions,
            tools=[],
            knowledge=[],
            memory_enabled=False,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Instructions:" in result
        assert "..." in result  # Should be truncated
        assert len(long_instructions) > 150  # Confirm it was long enough to truncate

    def test_formats_tools_list(self, home_screen):
        """Test that tools are displayed as comma-separated list."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o",
            instructions=None,
            tools=["Code Interpreter", "File Search", "Mcp"],
            knowledge=[],
            memory_enabled=False,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Tools:" in result
        assert "Code Interpreter" in result
        assert "File Search" in result
        assert "Mcp" in result

    def test_formats_empty_tools(self, home_screen):
        """Test display when tools list is empty."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o",
            instructions=None,
            tools=[],
            knowledge=[],
            memory_enabled=False,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Tools:" in result
        assert "None" in result

    def test_formats_knowledge_list(self, home_screen):
        """Test that knowledge bases are displayed."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o",
            instructions=None,
            tools=[],
            knowledge=["kb_docs", "kb_manuals"],
            memory_enabled=False,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Knowledge:" in result
        assert "kb_docs" in result
        assert "kb_manuals" in result

    def test_formats_memory_enabled(self, home_screen):
        """Test memory enabled display."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o",
            instructions=None,
            tools=[],
            knowledge=[],
            memory_enabled=True,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Memory:" in result
        assert "Enabled" in result

    def test_formats_memory_disabled(self, home_screen):
        """Test memory disabled display."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o",
            instructions=None,
            tools=[],
            knowledge=[],
            memory_enabled=False,
            guardrails=[],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Memory:" in result
        assert "Disabled" in result

    def test_formats_guardrails(self, home_screen):
        """Test guardrails display."""
        agent = Agent(
            id="test",
            name="Test",
            version="1",
            agent_type="Prompt",
            created_at=datetime.now(),
            description=None,
            model="gpt-4o",
            instructions=None,
            tools=[],
            knowledge=[],
            memory_enabled=False,
            guardrails=["Content Filter", "Grounding"],
        )

        result = home_screen._format_agent_preview(agent)

        assert "Guardrails:" in result
        assert "Content Filter" in result
        assert "Grounding" in result
