"""Main Anvil TUI application."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from anvil.screens.home import HomeScreen


class AnvilApp(App[None]):
    """Anvil - Microsoft Foundry TUI manager."""

    TITLE = "Anvil"
    SUB_TITLE = "Microsoft Foundry Manager"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [  # noqa: RUF012
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]

    SCREENS = {"home": HomeScreen}  # noqa: RUF012

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen("home")

    def action_help(self) -> None:
        self.notify("Help: Press 'q' to quit, use arrow keys to navigate")


def main() -> None:
    """Entry point for the Anvil TUI."""
    app = AnvilApp()
    app.run()


if __name__ == "__main__":
    main()
