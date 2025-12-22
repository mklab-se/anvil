"""Home screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

from anvil.config import FoundrySelection


class HomeScreen(Screen[None]):
    """Main home screen displaying project overview."""

    CSS = """
    #connection-info {
        height: auto;
        padding: 1;
        margin-bottom: 1;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
    }

    #connection-label {
        color: $text-muted;
    }

    #project-name {
        text-style: bold;
        color: $primary;
    }

    #project-details {
        color: $text-muted;
    }
    """

    def __init__(self, current_selection: FoundrySelection | None = None) -> None:
        """Initialize the home screen.

        Args:
            current_selection: Current Foundry project selection.
        """
        super().__init__()
        self._selection = current_selection

    def compose(self) -> ComposeResult:
        with Container(id="home-container"):
            # Connection info bar
            if self._selection:
                with Container(id="connection-info"):
                    yield Static("Connected to:", id="connection-label")
                    yield Static(
                        f"{self._selection.project_name}",
                        id="project-name",
                    )
                    yield Static(
                        f"{self._selection.account_name} / {self._selection.subscription_name}",
                        id="project-details",
                    )
            else:
                with Container(id="connection-info"):
                    yield Static("Not connected to any project", id="connection-label")

            yield Static("Welcome to Anvil", id="welcome-title")
            yield Static(
                "Your Microsoft Foundry resource manager",
                id="welcome-subtitle",
            )
            with Horizontal(id="main-content"):
                with Vertical(id="sidebar"):
                    yield Label("Resources", classes="section-header")
                    yield ListView(
                        ListItem(Label("Agents")),
                        ListItem(Label("Deployments")),
                        ListItem(Label("Connections")),
                        ListItem(Label("Datasets")),
                        id="nav-list",
                    )
                with Vertical(id="content-area"):
                    yield Label("Getting Started", classes="section-header")
                    if self._selection:
                        yield Static(
                            f"You are connected to project '{self._selection.project_name}'.\n\n"
                            "Use the sidebar to explore your Foundry resources.\n"
                            "Press 'p' to switch to a different project.",
                            id="getting-started-text",
                        )
                    else:
                        yield Static(
                            "No project selected.\n\n"
                            "Press 'p' to select a Foundry project.",
                            id="getting-started-text",
                        )
