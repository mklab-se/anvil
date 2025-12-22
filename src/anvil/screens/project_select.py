"""Project selection screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container
from textual.screen import Screen
from textual.widgets import LoadingIndicator, Static
from textual.worker import Worker, WorkerState, get_current_worker

from anvil.services.foundry import FoundryAccount, FoundryProject, FoundryService
from anvil.widgets.searchable_list import SearchableList


class ProjectSelectScreen(Screen[FoundryProject | None]):
    """Screen for selecting a Foundry project.

    Returns the selected FoundryProject or None if cancelled.
    """

    BINDINGS = [  # noqa: RUF012
        Binding("escape", "cancel", "Back"),
        Binding("/", "focus_search", "Search"),
    ]

    CSS = """
    ProjectSelectScreen {
        align: center middle;
    }

    #select-container {
        width: 80;
        height: auto;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }

    #screen-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #account-info {
        text-align: center;
        color: $text-muted;
    }

    #status {
        text-align: center;
        color: $text-muted;
    }

    #error {
        text-align: center;
        color: $error;
        display: none;
    }

    #error.has-error {
        display: block;
    }

    #loading {
        height: 3;
    }
    """

    def __init__(
        self,
        foundry_service: FoundryService,
        account: FoundryAccount,
        highlight_project_name: str | None = None,
    ) -> None:
        """Initialize the project select screen.

        Args:
            foundry_service: Service for listing projects.
            account: The Foundry account to list projects from.
            highlight_project_name: Project name to highlight (last used).
        """
        super().__init__()
        self._service = foundry_service
        self._account = account
        self._highlight_name = highlight_project_name
        self._projects: list[FoundryProject] = []

    def compose(self) -> ComposeResult:
        with Center(), Container(id="select-container"):
            yield Static("Select Foundry Project", id="screen-title")
            yield Static(
                f"Account: {self._account.name}", id="account-info"
            )
            yield Static("Loading projects...", id="status")
            yield Static("", id="error")
            with Center():
                yield LoadingIndicator(id="loading")
            yield SearchableList[FoundryProject](
                placeholder="Type to filter projects...",
                highlight_value=self._highlight_name,
                id="project-list",
            )

    def on_mount(self) -> None:
        """Load projects on mount."""
        self.query_one("#project-list", SearchableList).display = False
        self.run_worker(self._fetch_projects, thread=True)

    def _fetch_projects(self) -> list[FoundryProject]:
        """Fetch projects in background thread."""
        worker = get_current_worker()
        if worker.is_cancelled:
            return []
        return self._service.list_projects(
            resource_group=self._account.resource_group,
            account_name=self._account.name,
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.state == WorkerState.SUCCESS:
            self._projects = event.worker.result or []
            self._show_projects()
        elif event.state == WorkerState.ERROR:
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#status", Static).update("Failed to load projects.")
            error_widget = self.query_one("#error", Static)
            error_widget.update(str(event.worker.error))
            error_widget.add_class("has-error")

    def _show_projects(self) -> None:
        """Display loaded projects."""
        if not self._projects:
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#status", Static).update(
                "No projects found in this instance.\n"
                "Create one in the Azure portal first."
            )
            return

        # Build options list
        options: list[tuple[str, str]] = [
            (proj.display_name or proj.name, proj.name) for proj in self._projects
        ]

        # Update UI
        self.query_one("#loading", LoadingIndicator).display = False
        self.query_one("#status", Static).update(
            f"Found {len(self._projects)} project(s). "
            "Select one or type to filter."
        )

        search_list = self.query_one("#project-list", SearchableList)
        search_list.display = True
        search_list.set_options(options)

    def on_searchable_list_selected(self, event: SearchableList.Selected) -> None:
        """Handle project selection."""
        # Find the project by name
        for proj in self._projects:
            if proj.name == event.value:
                self.dismiss(proj)
                return

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(None)

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#project-list", SearchableList).focus_search()
