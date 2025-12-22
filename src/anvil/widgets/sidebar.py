"""Sidebar navigation widget for Anvil TUI."""

from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.events import Click


class SidebarItem(Static):
    """A single item in the sidebar."""

    DEFAULT_CSS = """
    SidebarItem {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    SidebarItem:hover {
        background: $primary 10%;
    }

    SidebarItem.selected {
        background: $primary 20%;
    }

    SidebarItem.selected .indicator {
        color: $primary;
    }

    SidebarItem.disabled {
        color: $text-muted;
    }
    """

    selected: reactive[bool] = reactive(False)

    def __init__(
        self,
        label: str,
        resource_id: str,
        icon: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize a sidebar item.

        Args:
            label: Display text for the item.
            resource_id: Identifier for the resource type.
            icon: Optional icon/indicator (e.g., "⚙" for settings).
            disabled: Whether the item is disabled (future feature).
        """
        super().__init__(**kwargs)
        self.label = label
        self.resource_id = resource_id
        self.icon = icon
        self._disabled = disabled
        if disabled:
            self.add_class("disabled")

    def render(self) -> str:
        """Render the sidebar item."""
        indicator = "▸ " if self.selected else "  "
        icon_suffix = f" {self.icon}" if self.icon else ""
        return f"{indicator}{self.label}{icon_suffix}"

    def watch_selected(self, selected: bool) -> None:
        """Update styling when selection changes."""
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")


class SidebarSeparator(Static):
    """A separator line in the sidebar."""

    DEFAULT_CSS = """
    SidebarSeparator {
        width: 100%;
        height: 1;
        color: $panel;
        padding: 0 1;
    }
    """

    def render(self) -> str:
        """Render a horizontal line."""
        return "─" * 12


class Sidebar(Widget, can_focus=True):
    """Navigation sidebar with resource categories."""

    DEFAULT_CSS = """
    Sidebar {
        width: 16;
        height: 100%;
        background: $surface;
        border-right: solid $panel;
        padding: 1 0;
    }

    Sidebar:focus {
        border-right: solid $primary;
    }

    Sidebar > Vertical {
        width: 100%;
        height: auto;
    }
    """

    BINDINGS = [  # noqa: RUF012
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    # Resource definitions: (label, resource_id, icon)
    # None = separator
    RESOURCES: ClassVar[list[tuple[str, str, str] | None]] = [
        ("Agents", "agents", ""),
        ("Models", "models", ""),
        None,  # Separator
        ("Knowledge", "knowledge", ""),
        ("Data", "data", ""),
        None,  # Separator
        ("Evaluations", "evaluations", ""),
        None,  # Separator
        ("Settings", "settings", ""),
    ]

    selected_index: reactive[int] = reactive(0)

    class Selected(Message):
        """Posted when a resource is selected."""

        def __init__(self, resource_id: str) -> None:
            """Initialize the selected message.

            Args:
                resource_id: The selected resource identifier.
            """
            self.resource_id = resource_id
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the sidebar."""
        super().__init__(**kwargs)
        self._items: list[SidebarItem] = []

    def compose(self) -> ComposeResult:
        """Create sidebar items."""
        with Vertical():
            for item in self.RESOURCES:
                if item is None:
                    yield SidebarSeparator()
                else:
                    label, resource_id, icon = item
                    sidebar_item = SidebarItem(label, resource_id, icon)
                    self._items.append(sidebar_item)
                    yield sidebar_item

    def on_mount(self) -> None:
        """Select the first item on mount."""
        self._update_selection()

    def watch_selected_index(self, index: int) -> None:
        """Update visual selection when index changes."""
        self._update_selection()

    def _update_selection(self) -> None:
        """Update which item appears selected."""
        for i, item in enumerate(self._items):
            item.selected = i == self.selected_index

    def action_cursor_down(self) -> None:
        """Move selection down."""
        if self.selected_index < len(self._items) - 1:
            self.selected_index += 1
            self._emit_selection()

    def action_cursor_up(self) -> None:
        """Move selection up."""
        if self.selected_index > 0:
            self.selected_index -= 1
            self._emit_selection()

    def action_select(self) -> None:
        """Confirm selection of current item."""
        self._emit_selection()

    def _emit_selection(self) -> None:
        """Post a Selected message for the current item."""
        if 0 <= self.selected_index < len(self._items):
            item = self._items[self.selected_index]
            self.post_message(self.Selected(item.resource_id))

    def on_click(self, event: "Click") -> None:
        """Handle clicks on sidebar items."""
        # Find which item was clicked
        for i, item in enumerate(self._items):
            if item.region.contains(event.x, event.y):
                self.selected_index = i
                self._emit_selection()
                break

    @property
    def selected_resource(self) -> str | None:
        """Return the currently selected resource ID."""
        if 0 <= self.selected_index < len(self._items):
            return self._items[self.selected_index].resource_id
        return None
