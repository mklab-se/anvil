"""Home screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static


class HomeScreen(Screen[None]):
    """Main home screen displaying project overview."""

    def compose(self) -> ComposeResult:
        with Container(id="home-container"):
            yield Static("Welcome to Anvil", id="welcome-title")
            yield Static(
                "Your Microsoft Foundry resource manager",
                id="welcome-subtitle",
            )
            with Horizontal(id="main-content"):
                with Vertical(id="sidebar"):
                    yield Label("Resources", classes="section-header")
                    yield ListView(
                        ListItem(Label("Projects")),
                        ListItem(Label("Deployments")),
                        ListItem(Label("Agents")),
                        ListItem(Label("Settings")),
                        id="nav-list",
                    )
                with Vertical(id="content-area"):
                    yield Label("Getting Started", classes="section-header")
                    yield Static(
                        "Connect to Microsoft Foundry to manage your projects and resources.\n\n"
                        "Use the sidebar to navigate between different resource types.",
                        id="getting-started-text",
                    )
