"""Authentication screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container
from textual.screen import Screen
from textual.widgets import Button, LoadingIndicator, Static

from anvil.services.auth import AuthService, AuthStatus


class AuthScreen(Screen[bool]):
    """Authentication status and login screen.

    Returns True if authentication succeeded, False otherwise.
    """

    BINDINGS = [  # noqa: RUF012
        Binding("escape", "quit", "Quit"),
    ]

    CSS = """
    AuthScreen {
        align: center middle;
    }

    #auth-container {
        width: 60;
        height: auto;
        padding: 2 4;
        border: solid $primary;
        background: $surface;
    }

    #auth-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        padding-bottom: 1;
    }

    #auth-status {
        text-align: center;
        padding: 1;
        color: $text-muted;
    }

    #auth-error {
        text-align: center;
        padding: 1;
        color: $error;
    }

    #login-btn {
        width: 100%;
        margin-top: 1;
    }

    #loading {
        height: 3;
    }
    """

    def __init__(self, auth_service: AuthService) -> None:
        """Initialize the auth screen.

        Args:
            auth_service: The authentication service to use.
        """
        super().__init__()
        self._auth_service = auth_service

    def compose(self) -> ComposeResult:
        with Center(), Container(id="auth-container"):
            yield Static("Authentication Required", id="auth-title")
            yield Static("Checking authentication status...", id="auth-status")
            yield Static("", id="auth-error")
            with Center():
                yield LoadingIndicator(id="loading")
            yield Button("Login with Azure", id="login-btn", variant="primary")

    def on_mount(self) -> None:
        """Check current auth status on mount."""
        self.query_one("#login-btn", Button).display = False
        self._check_auth()

    def _check_auth(self) -> None:
        """Check if already authenticated."""
        result = self._auth_service.check_auth_status()

        if result.status == AuthStatus.AUTHENTICATED:
            self.dismiss(True)
        else:
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#auth-status", Static).update(
                "Not authenticated. Click to login via browser."
            )
            self.query_one("#login-btn", Button).display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle login button press."""
        if event.button.id == "login-btn":
            self._do_login()

    def _do_login(self) -> None:
        """Initiate login flow."""
        self.query_one("#login-btn", Button).display = False
        self.query_one("#loading", LoadingIndicator).display = True
        self.query_one("#auth-status", Static).update("Opening browser for login...")
        self.query_one("#auth-error", Static).update("")

        # Run login (this will block while browser is open)
        result = self._auth_service.login()

        if result.status == AuthStatus.AUTHENTICATED:
            self.dismiss(True)
        else:
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#login-btn", Button).display = True
            self.query_one("#auth-status", Static).update("Login failed. Try again.")
            self.query_one("#auth-error", Static).update(result.error_message or "")

    def action_quit(self) -> None:
        """Handle quit action."""
        self.dismiss(False)
