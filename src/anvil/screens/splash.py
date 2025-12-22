"""Splash screen for Anvil TUI."""

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Static

ANVIL_LOGO = r"""
     __________________________
   /                          /|
  /                          / +------__
 /__________________________/ /________/\
 |                          ||________|_/
 |__________________________|
         |          |
   ______|          |__________
  /      |          |         /|
 /                           / |
/___________________________/  |
|                           |  |
|          Forged by MKLab  | /
|___________________________|/
"""


class SplashScreen(Screen[None]):
    """Splash screen showing the Anvil logo."""

    CSS = """
    SplashScreen {
        background: $background;
        align: center middle;
    }

    #splash-container {
        width: auto;
        height: auto;
        padding: 2 4;
    }

    #logo {
        color: $primary;
        text-align: center;
    }

    #title {
        color: $text;
        text-align: center;
        text-style: bold;
        padding-top: 1;
    }

    #subtitle {
        color: $text-muted;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the splash screen layout."""
        with Center(), Vertical(id="splash-container"):
            yield Static(ANVIL_LOGO, id="logo")
            yield Static("A N V I L", id="title")
            yield Static("Microsoft Foundry Manager", id="subtitle")

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
