"""Subscription selection screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container
from textual.screen import Screen
from textual.widgets import LoadingIndicator, Static

from anvil.services.subscriptions import Subscription, SubscriptionService
from anvil.widgets.searchable_list import SearchableList


class SubscriptionSelectScreen(Screen[Subscription | None]):
    """Screen for selecting an Azure subscription.

    Returns the selected Subscription or None if cancelled.
    """

    BINDINGS = [  # noqa: RUF012
        Binding("escape", "cancel", "Cancel"),
        Binding("/", "focus_search", "Search"),
    ]

    CSS = """
    SubscriptionSelectScreen {
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
        subscription_service: SubscriptionService,
        highlight_subscription_id: str | None = None,
    ) -> None:
        """Initialize the subscription select screen.

        Args:
            subscription_service: Service for listing subscriptions.
            highlight_subscription_id: Subscription ID to highlight (last used).
        """
        super().__init__()
        self._service = subscription_service
        self._highlight_id = highlight_subscription_id
        self._subscriptions: list[Subscription] = []

    def compose(self) -> ComposeResult:
        with Center(), Container(id="select-container"):
            yield Static("Select Azure Subscription", id="screen-title")
            yield Static("Loading subscriptions...", id="status")
            yield Static("", id="error")
            with Center():
                yield LoadingIndicator(id="loading")
            yield SearchableList[Subscription](
                placeholder="Type to filter subscriptions...",
                highlight_value=self._highlight_id,
                id="subscription-list",
            )

    def on_mount(self) -> None:
        """Load subscriptions on mount."""
        self.query_one("#subscription-list", SearchableList).display = False
        self._load_subscriptions()

    def _load_subscriptions(self) -> None:
        """Fetch and display subscriptions."""
        try:
            self._subscriptions = self._service.list_subscriptions()

            if not self._subscriptions:
                self.query_one("#loading", LoadingIndicator).display = False
                self.query_one("#status", Static).update(
                    "No subscriptions found. Check your Azure permissions."
                )
                return

            # Build options list
            options: list[tuple[str, str]] = [
                (f"{sub.display_name} ({sub.subscription_id[:8]}...)", sub.subscription_id)
                for sub in self._subscriptions
            ]

            # Update UI
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#status", Static).update(
                f"Found {len(self._subscriptions)} subscription(s). "
                "Select one or type to filter."
            )

            search_list = self.query_one("#subscription-list", SearchableList)
            search_list.display = True
            search_list.set_options(options)

        except Exception as e:
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#status", Static).update("Failed to load subscriptions.")
            self.query_one("#error", Static).update(str(e))

    def on_searchable_list_selected(self, event: SearchableList.Selected) -> None:
        """Handle subscription selection."""
        # Find the subscription by ID
        for sub in self._subscriptions:
            if sub.subscription_id == event.value:
                self.dismiss(sub)
                return

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(None)

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#subscription-list", SearchableList).focus_search()
