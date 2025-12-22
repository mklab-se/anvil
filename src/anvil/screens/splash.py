"""Splash screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Static

ANVIL_LOGO = """\
  █████╗ ███╗   ██╗██╗   ██╗██╗██╗
 ██╔══██╗████╗  ██║██║   ██║██║██║
 ███████║██╔██╗ ██║██║   ██║██║██║
 ██╔══██║██║╚██╗██║╚██╗ ██╔╝██║██║
 ██║  ██║██║ ╚████║ ╚████╔╝ ██║███████╗
 ╚═╝  ╚═╝╚═╝  ╚═══╝  ╚═══╝  ╚═╝╚══════╝\
"""


class SplashScreen(Screen[None]):
    """Splash screen showing the Anvil logo."""

    CSS = """
    SplashScreen {
        background: $background;
        align: center middle;
    }

    #splash-content {
        width: auto;
        height: auto;
        align: center middle;
    }

    #logo {
        color: $primary;
        width: auto;
        height: auto;
    }

    #subtitle {
        color: $text-muted;
        width: auto;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the splash screen layout."""
        with Container(id="splash-content"):
            yield Static(ANVIL_LOGO, id="logo")
            yield Static("Your tool in the foundry", id="subtitle")

    def on_mount(self) -> None:
        """Set timer to dismiss splash after delay."""
        self.set_timer(2.0, self._dismiss_splash)

    def _dismiss_splash(self) -> None:
        """Dismiss the splash screen."""
        self.dismiss()

    def on_key(self) -> None:
        """Allow any key press to skip the splash."""
        self._dismiss_splash()

    def on_click(self) -> None:
        """Allow click to skip the splash."""
        self._dismiss_splash()
