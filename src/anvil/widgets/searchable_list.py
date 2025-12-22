"""Searchable list widget for Anvil."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option


class SearchableList[T](Widget):
    """A searchable OptionList with filtering."""

    DEFAULT_CSS = """
    SearchableList {
        height: auto;
        max-height: 100%;
    }

    SearchableList > Vertical {
        height: auto;
        max-height: 100%;
    }

    SearchableList Input {
        margin-bottom: 1;
    }

    SearchableList OptionList {
        height: 8;
    }

    SearchableList .highlighted {
        background: $primary-darken-2;
    }
    """

    class Selected(Message):
        """Posted when an option is selected."""

        def __init__(self, value: Any, label: str) -> None:
            """Initialize the selected message.

            Args:
                value: The value associated with the selected option.
                label: The display label of the selected option.
            """
            self.value = value
            self.label = label
            super().__init__()

    def __init__(
        self,
        placeholder: str = "Type to search...",
        highlight_value: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the searchable list.

        Args:
            placeholder: Placeholder text for the search input.
            highlight_value: Value to highlight (e.g., last selection).
            **kwargs: Additional widget arguments.
        """
        super().__init__(**kwargs)
        self._placeholder = placeholder
        self._highlight_value = highlight_value
        self._all_options: list[tuple[str, Any]] = []  # (label, value)
        self._filtered_options: list[tuple[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(placeholder=self._placeholder, id="search-input")
            yield OptionList(id="options")

    def on_mount(self) -> None:
        """Focus the option list on mount."""
        self.query_one("#options", OptionList).focus()

    def set_options(self, options: list[tuple[str, Any]]) -> None:
        """Set the list of options.

        Args:
            options: List of (label, value) tuples.
        """
        self._all_options = options
        self._update_display("")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter options based on search input."""
        self._update_display(event.value.lower())

    def _update_display(self, query: str) -> None:
        """Update displayed options based on filter.

        Args:
            query: Search query (lowercase).
        """
        option_list = self.query_one("#options", OptionList)
        option_list.clear_options()

        self._filtered_options = []
        highlight_index: int | None = None

        for label, value in self._all_options:
            if not query or query in label.lower():
                self._filtered_options.append((label, value))
                idx = len(self._filtered_options) - 1
                option_list.add_option(Option(label, id=str(idx)))

                # Check if this should be highlighted (last used)
                if self._highlight_value is not None and value == self._highlight_value:
                    highlight_index = idx

        # Pre-select the previously used option, or first option if none
        if highlight_index is not None:
            option_list.highlighted = highlight_index
        elif self._filtered_options:
            option_list.highlighted = 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option_index is not None and event.option_index < len(self._filtered_options):
            label, value = self._filtered_options[event.option_index]
            self.post_message(self.Selected(value, label))

    def focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    @property
    def option_count(self) -> int:
        """Return the number of currently displayed options."""
        return len(self._filtered_options)
