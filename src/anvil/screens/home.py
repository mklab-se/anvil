"""Home screen for Anvil TUI."""

from azure.core.credentials import TokenCredential
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static
from textual.worker import Worker, WorkerState, get_current_worker

from anvil.config import FoundrySelection
from anvil.services.project_client import Agent, Deployment, ProjectClientService
from anvil.widgets.sidebar import Sidebar


class HomeScreen(Screen[None]):
    """Main home screen with sidebar navigation and resource list."""

    BINDINGS = [  # noqa: RUF012
        Binding("tab", "focus_next", "Next pane", show=False),
        Binding("shift+tab", "focus_previous", "Prev pane", show=False),
        Binding("/", "focus_search", "Search"),
        Binding("r", "refresh", "Refresh"),
        Binding("n", "new", "New"),
    ]

    CSS = """
    HomeScreen {
        layout: grid;
        grid-size: 1;
    }

    #main-container {
        width: 100%;
        height: 100%;
    }

    /* Resource header */
    #resource-header {
        height: 3;
        padding: 1;
        background: $surface;
    }

    #resource-title {
        text-style: bold;
        color: $text;
    }

    #create-btn {
        dock: right;
        background: $primary;
        color: $background;
        padding: 0 2;
        text-style: bold;
    }

    #create-btn:hover {
        background: $primary-lighten-1;
    }

    /* List container */
    #list-container {
        width: 1fr;
        height: 100%;
        background: $background;
    }

    /* Search input */
    #search-input {
        margin: 0 1;
        height: 3;
    }

    /* Resource table */
    #resource-table {
        height: 1fr;
        margin: 0 1;
    }

    #resource-table > .datatable--header {
        background: $panel;
        color: $text-muted;
        text-style: bold;
    }

    #resource-table > .datatable--cursor {
        background: $primary 20%;
    }

    /* Preview panel */
    #preview-panel {
        width: 40;
        height: 100%;
        background: $surface;
        border-left: solid $panel;
        padding: 1;
        display: none;
        overflow-y: auto;
    }

    #preview-panel.visible {
        display: block;
    }

    #preview-title {
        text-style: bold;
        color: $primary;
        padding-bottom: 1;
    }

    #preview-content {
        color: $text;
    }

    .preview-label {
        color: $text-muted;
    }

    .preview-value {
        color: $text;
        padding-bottom: 1;
    }

    /* Empty state */
    #empty-state {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }

    /* Loading state */
    #loading-state {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        current_selection: FoundrySelection | None = None,
        credential: TokenCredential | None = None,
    ) -> None:
        """Initialize the home screen.

        Args:
            current_selection: Current Foundry project selection.
            credential: Azure credential for API calls.
        """
        super().__init__()
        self._selection = current_selection
        self._credential = credential
        self._current_resource = "agents"
        self._project_client: ProjectClientService | None = None
        self._agents: list[Agent] = []
        self._deployments: list[Deployment] = []

        # Initialize project client if we have selection and credential
        if self._selection and self._credential and self._selection.project_endpoint:
            self._project_client = ProjectClientService(
                endpoint=self._selection.project_endpoint,
                credential=self._credential,
            )

    def compose(self) -> ComposeResult:
        """Create the home screen layout."""
        yield Header()
        with Horizontal(id="main-container"):
            yield Sidebar(id="sidebar")
            with Vertical(id="list-container"):
                with Horizontal(id="resource-header"):
                    yield Static("Agents", id="resource-title")
                    yield Static("+ Create", id="create-btn")
                yield Input(placeholder="/ Search...", id="search-input")
                yield DataTable(id="resource-table", zebra_stripes=True, cursor_type="row")
            with Container(id="preview-panel"):
                yield Static("", id="preview-title")
                yield Static("", id="preview-content")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the table on mount."""
        self._setup_agents_table()
        # Load real data if we have a project client, otherwise use placeholder
        if self._project_client:
            self._load_agents()
        else:
            self._load_placeholder_data()

    def _load_agents(self) -> None:
        """Load agents from the SDK using a background worker."""
        self.run_worker(self._fetch_agents, thread=True, name="fetch_agents")

    def _fetch_agents(self) -> list[Agent]:
        """Fetch agents in background thread."""
        worker = get_current_worker()
        if worker.is_cancelled:
            return []
        if self._project_client:
            return self._project_client.list_agents()
        return []

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.worker.name == "fetch_agents":
            if event.state == WorkerState.SUCCESS:
                self._agents = event.worker.result or []
                # Only populate if we're still on agents view
                if self._current_resource == "agents":
                    self._populate_agents_table()
            elif event.state == WorkerState.ERROR:
                self.notify(f"Failed to load agents: {event.worker.error}", severity="error")
                if self._current_resource == "agents":
                    self._load_placeholder_data()
        elif event.worker.name == "fetch_deployments":
            if event.state == WorkerState.SUCCESS:
                self._deployments = event.worker.result or []
                # Only populate if we're still on models view
                if self._current_resource == "models":
                    self._populate_models_table()
            elif event.state == WorkerState.ERROR:
                self.notify(f"Failed to load models: {event.worker.error}", severity="error")
                if self._current_resource == "models":
                    self._load_placeholder_models()

    def _load_models(self) -> None:
        """Load model deployments from the SDK using a background worker."""
        self.run_worker(self._fetch_deployments, thread=True, name="fetch_deployments")

    def _fetch_deployments(self) -> list[Deployment]:
        """Fetch deployments in background thread."""
        worker = get_current_worker()
        if worker.is_cancelled:
            return []
        if self._project_client:
            return self._project_client.list_deployments()
        return []

    def _populate_models_table(self) -> None:
        """Populate the table with fetched deployments."""
        table = self.query_one("#resource-table", DataTable)
        table.clear()

        if not self._deployments:
            self.notify("No models found", severity="information")
            return

        for deployment in self._deployments:
            table.add_row(
                deployment.name,
                deployment.model_name,
                deployment.model_version,
                deployment.deployment_type,
                deployment.model_publisher,
                key=deployment.name,
            )

    def _load_placeholder_models(self) -> None:
        """Load placeholder model data for demonstration."""
        self._deployments = [
            Deployment(
                name="gpt-4o",
                model_name="gpt-4o",
                model_version="2024-08-06",
                model_publisher="OpenAI",
                deployment_type="Global Standard",
                capacity=100,
                capabilities=["Chat Completion"],
            ),
            Deployment(
                name="gpt-4o-mini",
                model_name="gpt-4o-mini",
                model_version="2024-07-18",
                model_publisher="OpenAI",
                deployment_type="Global Standard",
                capacity=150,
                capabilities=["Chat Completion"],
            ),
            Deployment(
                name="text-embedding-3-large",
                model_name="text-embedding-3-large",
                model_version="1",
                model_publisher="OpenAI",
                deployment_type="Global Standard",
                capacity=500,
                capabilities=["Embeddings"],
            ),
        ]
        # Sort by name
        self._deployments.sort(key=lambda d: d.name.lower())
        self._populate_models_table()

    def _populate_agents_table(self) -> None:
        """Populate the table with fetched agents."""
        table = self.query_one("#resource-table", DataTable)
        table.clear()

        if not self._agents:
            self.notify("No agents found", severity="information")
            return

        for agent in self._agents:
            created_str = ""
            if agent.created_at:
                created_str = agent.created_at.strftime("%m/%d/%y, %I:%M %p")

            # Truncate description for table display
            description = agent.description or ""
            if len(description) > 40:
                description = description[:37] + "..."

            # Count tools and knowledge bases
            tools_count = str(len(agent.tools)) if agent.tools else "0"
            kb_count = str(len(agent.knowledge)) if agent.knowledge else "0"

            table.add_row(
                agent.name,
                agent.version,
                agent.agent_type,
                tools_count,
                kb_count,
                created_str,
                description,
                key=agent.id,
            )

    def _setup_agents_table(self) -> None:
        """Configure the table for Agents resource."""
        table = self.query_one("#resource-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Version", "Type", "Tools", "KB", "Created", "Description")

    def _setup_models_table(self) -> None:
        """Configure the table for Models resource."""
        table = self.query_one("#resource-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Model", "Version", "Type", "Publisher")

    def _load_placeholder_data(self) -> None:
        """Load placeholder data for demonstration."""
        from datetime import datetime

        if self._current_resource == "agents":
            # Create realistic placeholder Agent objects
            self._agents = [
                Agent(
                    id="agent-001",
                    name="irma",
                    version="-",
                    agent_type="Assistant",
                    created_at=datetime(2025, 12, 18, 16, 58),
                    description="Customer service assistant for handling inquiries",
                    model="gpt-4o",
                    instructions="You are a helpful customer service agent. Answer questions politely and accurately.",
                    tools=["Code Interpreter", "File Search"],
                    knowledge=["vs_abc123"],
                    memory_enabled=True,
                    guardrails=["Content Filter"],
                ),
                Agent(
                    id="agent-002",
                    name="code-helper",
                    version="-",
                    agent_type="Assistant",
                    created_at=datetime(2025, 12, 18, 15, 9),
                    description="Programming assistant with code execution",
                    model="gpt-4o",
                    instructions="You are a programming assistant. Help users write, debug, and understand code.",
                    tools=["Code Interpreter"],
                    knowledge=[],
                    memory_enabled=False,
                    guardrails=[],
                ),
                Agent(
                    id="agent-003",
                    name="doc-search",
                    version="-",
                    agent_type="Assistant",
                    created_at=datetime(2025, 12, 17, 11, 24),
                    description="Documentation search and Q&A",
                    model="gpt-4o-mini",
                    instructions="Search the documentation to answer user questions accurately.",
                    tools=["File Search", "Bing Grounding"],
                    knowledge=["vs_docs001", "vs_docs002"],
                    memory_enabled=True,
                    guardrails=["Content Filter", "Grounding"],
                ),
                Agent(
                    id="agent-004",
                    name="data-analyst",
                    version="-",
                    agent_type="Assistant",
                    created_at=datetime(2025, 12, 16, 9, 30),
                    description="Analyzes data and creates visualizations",
                    model="gpt-4o",
                    instructions="Analyze data files and create charts and insights.",
                    tools=["Code Interpreter", "File Search"],
                    knowledge=["vs_data123"],
                    memory_enabled=False,
                    guardrails=[],
                ),
            ]
            self._populate_agents_table()
        elif self._current_resource == "models":
            self._load_placeholder_models()

    def _cancel_pending_workers(self) -> None:
        """Cancel any running data fetch workers."""
        for worker in self.workers:
            if worker.name in ("fetch_agents", "fetch_deployments"):
                worker.cancel()

    def on_sidebar_selected(self, event: Sidebar.Selected) -> None:
        """Handle sidebar navigation."""
        # Cancel any pending data fetches to prevent race conditions
        self._cancel_pending_workers()

        self._current_resource = event.resource_id
        title = self.query_one("#resource-title", Static)

        if event.resource_id == "agents":
            title.update("Agents")
            self._setup_agents_table()
            if self._project_client:
                self._load_agents()
            else:
                self._load_placeholder_data()
        elif event.resource_id == "models":
            title.update("Models")
            self._setup_models_table()
            if self._project_client:
                self._load_models()
            else:
                self._load_placeholder_models()
        elif event.resource_id == "knowledge":
            title.update("Knowledge")
            self._setup_agents_table()  # Reuse for now
            self._load_placeholder_data()
        elif event.resource_id == "data":
            title.update("Data")
            self._setup_agents_table()  # Reuse for now
            self._load_placeholder_data()
        elif event.resource_id == "evaluations":
            title.update("Evaluations")
            self._setup_agents_table()  # Reuse for now
            self._load_placeholder_data()
        elif event.resource_id == "settings":
            title.update("Settings")
            self._setup_agents_table()  # Reuse for now
            self._load_placeholder_data()
        else:
            title.update(event.resource_id.title())
            self._load_placeholder_data()

    def _get_agent_by_id(self, agent_id: str) -> Agent | None:
        """Find an agent by its ID."""
        for agent in self._agents:
            if agent.id == agent_id:
                return agent
        return None

    def _get_deployment_by_name(self, name: str) -> Deployment | None:
        """Find a deployment by its name."""
        for deployment in self._deployments:
            if deployment.name == name:
                return deployment
        return None

    def _format_deployment_preview(self, deployment: Deployment) -> str:
        """Format deployment details for the preview panel."""
        lines = []

        # Model info
        lines.append(f"[b]Model:[/b] {deployment.model_name}")
        lines.append(f"[b]Version:[/b] {deployment.model_version}")
        lines.append(f"[b]Publisher:[/b] {deployment.model_publisher}")

        # Deployment details
        lines.append(f"\n[b]Deployment Type:[/b] {deployment.deployment_type}")
        lines.append(f"[b]Capacity:[/b] {deployment.capacity}")

        # Capabilities
        if deployment.capabilities:
            caps_str = ", ".join(deployment.capabilities)
            lines.append(f"\n[b]Capabilities:[/b]\n{caps_str}")
        else:
            lines.append("\n[b]Capabilities:[/b] None")

        return "\n".join(lines)

    def _format_agent_preview(self, agent: Agent) -> str:
        """Format agent details for the preview panel."""
        lines = []

        # ── Configuration ──
        lines.append("[b]── Configuration ──[/b]")
        lines.append(f"Model: {agent.model or 'Not set'}")
        if agent.temperature is not None:
            lines.append(f"Temperature: {agent.temperature}")
        if agent.top_p is not None:
            lines.append(f"Top-P: {agent.top_p}")

        # ── Instructions ──
        lines.append("\n[b]── Instructions ──[/b]")
        if agent.instructions:
            instructions = agent.instructions
            if len(instructions) > 150:
                instructions = instructions[:147] + "..."
            lines.append(instructions)
        else:
            lines.append("None")

        # ── Tools ──
        lines.append("\n[b]── Tools ──[/b]")
        if agent.tool_configs:
            for tool in agent.tool_configs:
                # Format indicator based on approval status
                if tool.type == "mcp":
                    # Show MCP tool with server label
                    label = tool.server_label or "unknown"
                    # Trim kb_ prefix for cleaner display
                    if label.startswith("kb_"):
                        label = label[3:]
                    lines.append(f"  MCP: {label}")
                    # Show approval status on separate line
                    if tool.require_approval == "always":
                        lines.append("    ⚠ Approval required")
                    else:
                        lines.append("    ✓ No approval needed")
                else:
                    lines.append(f"  {tool.display_name}")
        elif agent.tools:
            # Fallback to simple tool names
            for tool_name in agent.tools:
                lines.append(f"  {tool_name}")
        else:
            lines.append("  None")

        # ── Knowledge ──
        lines.append("\n[b]── Knowledge ──[/b]")
        if agent.knowledge:
            for k in agent.knowledge:
                display_k = k[:25] + "..." if len(k) > 25 else k
                lines.append(f"  - {display_k}")
        else:
            lines.append("  None")

        # ── Safety & Settings ──
        lines.append("\n[b]── Safety & Settings ──[/b]")
        memory_status = "Enabled" if agent.memory_enabled else "Disabled"
        lines.append(f"Memory: {memory_status}")
        if agent.guardrails:
            guardrails_str = ", ".join(agent.guardrails)
            lines.append(f"Guardrails: {guardrails_str}")
        else:
            lines.append("Guardrails: None")

        # ── Metadata ──
        if agent.full_metadata and len(agent.full_metadata) > 0:
            lines.append("\n[b]── Metadata ──[/b]")
            for key, value in agent.full_metadata.items():
                # Truncate long values
                display_value = value[:30] + "..." if len(value) > 30 else value
                lines.append(f"  {key}: {display_value}")

        # ── IDs ──
        lines.append("\n[b]── IDs ──[/b]")
        lines.append(f"Agent: {agent.id}")
        lines.append(f"Version: {agent.version}")

        return "\n".join(lines)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show preview panel when a row is selected."""
        table = self.query_one("#resource-table", DataTable)
        row_data = table.get_row(event.row_key)

        preview = self.query_one("#preview-panel", Container)
        preview.add_class("visible")

        title = self.query_one("#preview-title", Static)
        content = self.query_one("#preview-content", Static)

        if self._current_resource == "agents" and row_data:
            # Row format: [name, version, type, tools, kb, created, description]
            name = row_data[0]
            title.update(str(name))

            # Try to get full agent details
            agent = self._get_agent_by_id(str(event.row_key.value)) if event.row_key else None
            if agent:
                content.update(self._format_agent_preview(agent))
            else:
                # Fallback for placeholder data
                _, version, agent_type, tools, kb, created, description = row_data
                content.update(
                    f"[b]Version:[/b] {version}\n"
                    f"[b]Type:[/b] {agent_type}\n"
                    f"[b]Tools:[/b] {tools}\n"
                    f"[b]Knowledge:[/b] {kb}\n"
                    f"[b]Created:[/b] {created}\n"
                    f"[b]Description:[/b] {description}\n\n"
                    "[dim]Press Enter to edit[/dim]\n"
                    "[dim]Press d to delete[/dim]"
                )
        elif self._current_resource == "models" and row_data:
            name = row_data[0]
            title.update(str(name))

            # Try to get full deployment details
            deployment = self._get_deployment_by_name(str(event.row_key.value)) if event.row_key else None
            if deployment:
                content.update(self._format_deployment_preview(deployment))
            else:
                # Fallback for table data only
                _, model, version, dep_type, publisher = row_data
                content.update(
                    f"[b]Model:[/b] {model}\n"
                    f"[b]Version:[/b] {version}\n"
                    f"[b]Type:[/b] {dep_type}\n"
                    f"[b]Publisher:[/b] {publisher}"
                )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update preview when row highlight changes."""
        if event.row_key is not None:
            table = self.query_one("#resource-table", DataTable)
            row_data = table.get_row(event.row_key)

            preview = self.query_one("#preview-panel", Container)
            preview.add_class("visible")

            title = self.query_one("#preview-title", Static)
            content = self.query_one("#preview-content", Static)

            if self._current_resource == "agents" and row_data:
                # Row format: [name, version, type, tools, kb, created, description]
                name = row_data[0]
                title.update(str(name))

                # Try to get full agent details
                agent = self._get_agent_by_id(str(event.row_key.value)) if event.row_key else None
                if agent:
                    content.update(self._format_agent_preview(agent))
                else:
                    # Fallback for placeholder data
                    _, version, agent_type, tools, kb, created, description = row_data
                    content.update(
                        f"[b]Version:[/b] {version}\n"
                        f"[b]Type:[/b] {agent_type}\n"
                        f"[b]Tools:[/b] {tools}\n"
                        f"[b]Knowledge:[/b] {kb}\n"
                        f"[b]Created:[/b] {created}\n"
                        f"[b]Description:[/b] {description}\n\n"
                        "[dim]Press Enter to edit[/dim]\n"
                        "[dim]Press d to delete[/dim]"
                    )
            elif self._current_resource == "models" and row_data:
                name = row_data[0]
                title.update(str(name))

                # Try to get full deployment details
                deployment = self._get_deployment_by_name(str(event.row_key.value)) if event.row_key else None
                if deployment:
                    content.update(self._format_deployment_preview(deployment))
                else:
                    # Fallback for table data only
                    _, model, version, dep_type, publisher = row_data
                    content.update(
                        f"[b]Model:[/b] {model}\n"
                        f"[b]Version:[/b] {version}\n"
                        f"[b]Type:[/b] {dep_type}\n"
                        f"[b]Publisher:[/b] {publisher}"
                    )

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_refresh(self) -> None:
        """Refresh the current resource list."""
        self._load_placeholder_data()
        self.notify("Refreshed")

    def action_new(self) -> None:
        """Create a new resource."""
        self.notify(f"Create new {self._current_resource[:-1]}")  # Remove 's'

    def action_focus_next(self) -> None:
        """Focus the next pane."""
        # Cycle: sidebar -> table -> search -> sidebar
        focused = self.focused
        if focused is None or focused.id == "sidebar":
            self.query_one("#resource-table", DataTable).focus()
        elif focused.id == "resource-table":
            self.query_one("#search-input", Input).focus()
        else:
            self.query_one("#sidebar", Sidebar).focus()

    def action_focus_previous(self) -> None:
        """Focus the previous pane."""
        focused = self.focused
        if focused is None or focused.id == "sidebar":
            self.query_one("#search-input", Input).focus()
        elif focused.id == "search-input":
            self.query_one("#resource-table", DataTable).focus()
        else:
            self.query_one("#sidebar", Sidebar).focus()
