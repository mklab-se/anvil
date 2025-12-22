"""Foundry account selection screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container
from textual.screen import Screen
from textual.widgets import LoadingIndicator, Static

from anvil.services.foundry import FoundryAccount, FoundryService
from anvil.widgets.searchable_list import SearchableList


class FoundrySelectScreen(Screen[FoundryAccount | None]):
    """Screen for selecting an Azure AI Foundry instance.

    Returns the selected FoundryAccount or None if cancelled.
    """

    BINDINGS = [  # noqa: RUF012
        Binding("escape", "cancel", "Back"),
        Binding("/", "focus_search", "Search"),
    ]

    CSS = """
    FoundrySelectScreen {
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
        highlight_account_name: str | None = None,
    ) -> None:
        """Initialize the foundry select screen.

        Args:
            foundry_service: Service for listing Foundry instances.
            highlight_account_name: Instance name to highlight (last used).
        """
        super().__init__()
        self._service = foundry_service
        self._highlight_name = highlight_account_name
        self._accounts: list[FoundryAccount] = []

    def compose(self) -> ComposeResult:
        with Center(), Container(id="select-container"):
            yield Static("Select Foundry Instance", id="screen-title")
            yield Static("Loading Foundry instances...", id="status")
            yield Static("", id="error")
            with Center():
                yield LoadingIndicator(id="loading")
            yield SearchableList[FoundryAccount](
                placeholder="Type to filter instances...",
                highlight_value=self._highlight_name,
                id="account-list",
            )

    def on_mount(self) -> None:
        """Load accounts on mount."""
        self.query_one("#account-list", SearchableList).display = False
        self._load_accounts()

    def _load_accounts(self) -> None:
        """Fetch and display Foundry instances."""
        try:
            self._accounts = self._service.list_accounts()

            if not self._accounts:
                self.query_one("#loading", LoadingIndicator).display = False
                self.query_one("#status", Static).update(
                    "No Foundry instances found in this subscription.\n"
                    "Create one in the Azure portal first."
                )
                return

            # Build options list
            options: list[tuple[str, str]] = [
                (f"{acc.name} ({acc.location})", acc.name) for acc in self._accounts
            ]

            # Update UI
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#status", Static).update(
                f"Found {len(self._accounts)} Foundry instance(s). "
                "Select one or type to filter."
            )

            search_list = self.query_one("#account-list", SearchableList)
            search_list.display = True
            search_list.set_options(options)

        except Exception as e:
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#status", Static).update("Failed to load Foundry instances.")
            self.query_one("#error", Static).update(str(e))

    def on_searchable_list_selected(self, event: SearchableList.Selected) -> None:
        """Handle instance selection."""
        # Find the account by name
        for acc in self._accounts:
            if acc.name == event.value:
                self.dismiss(acc)
                return

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(None)

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#account-list", SearchableList).focus_search()
