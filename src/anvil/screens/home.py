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
        width: 30;
        height: 100%;
        background: $surface;
        border-left: solid $panel;
        padding: 1;
        display: none;
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
                self._populate_agents_table()
            elif event.state == WorkerState.ERROR:
                self.notify(f"Failed to load agents: {event.worker.error}", severity="error")
                self._load_placeholder_data()
        elif event.worker.name == "fetch_deployments":
            if event.state == WorkerState.SUCCESS:
                self._deployments = event.worker.result or []
                self._populate_models_table()
            elif event.state == WorkerState.ERROR:
                self.notify(f"Failed to load models: {event.worker.error}", severity="error")
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
                deployment.model,
                deployment.version,
                deployment.status,
                key=deployment.name,
            )

    def _load_placeholder_models(self) -> None:
        """Load placeholder model data for demonstration."""
        table = self.query_one("#resource-table", DataTable)
        table.clear()
        table.add_rows(
            [
                ("gpt-4o", "gpt-4o", "2024-08-06", "Ready"),
                ("gpt-4o-mini", "gpt-4o-mini", "2024-07-18", "Ready"),
                ("text-embedding-3-large", "text-embedding-3-large", "1", "Ready"),
            ]
        )

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

            table.add_row(
                agent.name,
                agent.agent_type,
                created_str,
                key=agent.id,
            )

    def _setup_agents_table(self) -> None:
        """Configure the table for Agents resource."""
        table = self.query_one("#resource-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Type", "Created")

    def _setup_models_table(self) -> None:
        """Configure the table for Models resource."""
        table = self.query_one("#resource-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Model", "Version", "Status")

    def _load_placeholder_data(self) -> None:
        """Load placeholder data for demonstration."""
        table = self.query_one("#resource-table", DataTable)
        if self._current_resource == "agents":
            # Placeholder agent data
            table.add_rows(
                [
                    ("irma", "prompt", "12/18/25, 4:58 PM"),
                    ("irma-v3", "prompt", "12/18/25, 3:09 PM"),
                    ("testar", "prompt", "12/18/25, 3:09 PM"),
                    ("agent-smith", "prompt", "12/18/25, 12:39 PM"),
                    ("agent-doc", "prompt", "12/17/25, 11:24 AM"),
                    ("mr-bond", "prompt", "12/17/25, 12:23 PM"),
                ]
            )
        elif self._current_resource == "models":
            # Placeholder model data
            table.add_rows(
                [
                    ("gpt-4o", "gpt-4o", "2024-08-06", "Ready"),
                    ("gpt-4o-mini", "gpt-4o-mini", "2024-07-18", "Ready"),
                    ("text-embedding-3-large", "text-embedding-3-large", "1", "Ready"),
                ]
            )

    def on_sidebar_selected(self, event: Sidebar.Selected) -> None:
        """Handle sidebar navigation."""
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show preview panel when a row is selected."""
        table = self.query_one("#resource-table", DataTable)
        row_data = table.get_row(event.row_key)

        preview = self.query_one("#preview-panel", Container)
        preview.add_class("visible")

        title = self.query_one("#preview-title", Static)
        content = self.query_one("#preview-content", Static)

        if self._current_resource == "agents" and row_data:
            name, agent_type, created = row_data
            title.update(str(name))
            content.update(
                f"[b]Type:[/b] {agent_type}\n"
                f"[b]Created:[/b] {created}\n\n"
                "[dim]Press Enter to edit[/dim]\n"
                "[dim]Press d to delete[/dim]"
            )
        elif self._current_resource == "models" and row_data:
            name, model, version, status = row_data
            title.update(str(name))
            content.update(
                f"[b]Model:[/b] {model}\n"
                f"[b]Version:[/b] {version}\n"
                f"[b]Status:[/b] {status}\n\n"
                "[dim]Press Enter to view details[/dim]"
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
                name, agent_type, created = row_data
                title.update(str(name))
                content.update(
                    f"[b]Type:[/b] {agent_type}\n"
                    f"[b]Created:[/b] {created}\n\n"
                    "[dim]Press Enter to edit[/dim]\n"
                    "[dim]Press d to delete[/dim]"
                )
            elif self._current_resource == "models" and row_data:
                name, model, version, status = row_data
                title.update(str(name))
                content.update(
                    f"[b]Model:[/b] {model}\n"
                    f"[b]Version:[/b] {version}\n"
                    f"[b]Status:[/b] {status}\n\n"
                    "[dim]Press Enter to view details[/dim]"
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
