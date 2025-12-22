"""Main Anvil TUI application."""

from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from anvil.config import ConfigManager, FoundrySelection
from anvil.screens.auth import AuthScreen
from anvil.screens.foundry_select import FoundrySelectScreen
from anvil.screens.home import HomeScreen
from anvil.screens.project_select import ProjectSelectScreen
from anvil.screens.subscription_select import SubscriptionSelectScreen
from anvil.services.auth import AuthService, AuthStatus
from anvil.services.foundry import FoundryAccount, FoundryProject, FoundryService
from anvil.services.subscriptions import Subscription, SubscriptionService


class AnvilApp(App[None]):
    """Anvil - Microsoft Foundry TUI manager."""

    TITLE = "Anvil"
    SUB_TITLE = "Microsoft Foundry Manager"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [  # noqa: RUF012
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("p", "switch_project", "Switch Project"),
    ]

    def __init__(self) -> None:
        """Initialize the Anvil application."""
        super().__init__()
        self.auth_service = AuthService()
        self.config_manager = ConfigManager()
        self.current_selection: FoundrySelection | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Run startup flow on mount."""
        self._startup_flow()

    def _startup_flow(self) -> None:
        """Execute the startup authentication and selection flow."""
        # Step 1: Check/perform authentication
        if not self._ensure_authenticated():
            return

        # Step 2: Load config and check for cached selection
        config = self.config_manager.load()

        if config.last_selection and config.auto_connect_last:
            # Auto-connect to last selection
            self.current_selection = config.last_selection
            self._show_home()
            return

        # Step 3: Run selection flow
        self._run_selection_flow()

    def _ensure_authenticated(self) -> bool:
        """Check auth status, prompt login if needed.

        Returns:
            True if authenticated, False otherwise.
        """
        result = self.auth_service.check_auth_status()

        if result.status == AuthStatus.AUTHENTICATED:
            return True

        # Show auth screen and handle result
        def on_auth_result(authenticated: bool | None) -> None:
            if authenticated:
                # Continue with startup flow
                config = self.config_manager.load()
                if config.last_selection and config.auto_connect_last:
                    self.current_selection = config.last_selection
                    self._show_home()
                else:
                    self._run_selection_flow()
            else:
                self.exit()

        self.push_screen(AuthScreen(self.auth_service), on_auth_result)
        return False

    def _run_selection_flow(self) -> None:
        """Run the subscription -> account -> project selection flow."""
        # Get cached values for highlighting
        last_sub_id = self.config_manager.get_last_subscription_id()

        # Step 1: Select subscription
        subscription_service = SubscriptionService(self.auth_service.get_credential())

        def on_subscription_selected(subscription: Subscription | None) -> None:
            if subscription is None:
                self.exit()
                return
            self._select_foundry_account(subscription)

        self.push_screen(
            SubscriptionSelectScreen(
                subscription_service=subscription_service,
                highlight_subscription_id=last_sub_id,
            ),
            on_subscription_selected,
        )

    def _select_foundry_account(self, subscription: Subscription) -> None:
        """Show foundry account selection screen.

        Args:
            subscription: Selected subscription.
        """
        last_account = self.config_manager.get_last_account_name()
        foundry_service = FoundryService(
            credential=self.auth_service.get_credential(),
            subscription_id=subscription.subscription_id,
        )

        def on_account_selected(account: FoundryAccount | None) -> None:
            if account is None:
                # Go back to subscription selection
                self._run_selection_flow()
                return
            self._select_project(subscription, account, foundry_service)

        self.push_screen(
            FoundrySelectScreen(
                foundry_service=foundry_service,
                highlight_account_name=last_account,
            ),
            on_account_selected,
        )

    def _select_project(
        self,
        subscription: Subscription,
        account: FoundryAccount,
        foundry_service: FoundryService,
    ) -> None:
        """Show project selection screen.

        Args:
            subscription: Selected subscription.
            account: Selected Foundry account.
            foundry_service: Foundry service instance.
        """
        last_project = self.config_manager.get_last_project_name()

        def on_project_selected(project: FoundryProject | None) -> None:
            if project is None:
                # Go back to account selection
                self._select_foundry_account(subscription)
                return

            # Save selection and proceed
            selection = FoundrySelection(
                subscription_id=subscription.subscription_id,
                subscription_name=subscription.display_name,
                resource_group=account.resource_group,
                account_name=account.name,
                project_name=project.name,
                project_endpoint=project.endpoint,
                selected_at=datetime.now(),
            )
            self.config_manager.update_selection(selection)
            self.current_selection = selection
            self._show_home()

        self.push_screen(
            ProjectSelectScreen(
                foundry_service=foundry_service,
                account=account,
                highlight_project_name=last_project,
            ),
            on_project_selected,
        )

    def _show_home(self) -> None:
        """Show the home screen."""
        # Clear any existing screens and push home
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(HomeScreen(current_selection=self.current_selection))

    def action_help(self) -> None:
        """Show help notification."""
        self.notify("Press 'q' to quit, 'p' to switch project")

    def action_switch_project(self) -> None:
        """Switch to a different project."""
        if not self.auth_service.is_authenticated():
            self.notify("Not authenticated", severity="error")
            return

        # Run selection flow (will highlight last used values)
        self._run_selection_flow()


def main() -> None:
    """Entry point for the Anvil TUI."""
    app = AnvilApp()
    app.run()


if __name__ == "__main__":
    main()
