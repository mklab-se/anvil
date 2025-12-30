"""Agent edit/create screen for Anvil TUI."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Rule,
    Select,
    Static,
    TextArea,
)
from textual.worker import Worker, WorkerState

from anvil.services.project_client import Agent, Deployment, ProjectClientService, ToolConfig


class AgentEditScreen(Screen[Agent | None]):
    """Screen for editing or creating an agent."""

    BINDINGS = [  # noqa: RUF012
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    CSS = """
    #edit-container {
        width: 100%;
        height: 1fr;
        background: $background;
    }

    #form-scroll {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    /* Header area */
    #edit-header {
        height: 3;
        padding: 0 2;
        background: $surface;
        border-bottom: solid $panel;
    }

    #edit-title {
        text-style: bold;
        color: $text;
        padding: 1 0;
        width: 1fr;
    }

    /* Button bar */
    #button-bar {
        height: 3;
        padding: 0 2;
        background: $surface;
        border-top: solid $panel;
        align: right middle;
    }

    #button-bar Button {
        margin-left: 1;
    }

    .save-btn {
        background: $primary;
    }

    .cancel-btn {
        background: $surface;
        color: $text;
        border: solid $primary;
    }

    /* Form sections */
    .section-title {
        color: $primary;
        text-style: bold;
        padding: 1 0;
        margin-top: 1;
    }

    .form-row {
        height: auto;
        margin-bottom: 1;
    }

    .form-label {
        width: 15;
        color: $text-muted;
        padding-right: 1;
    }

    .form-field {
        width: 1fr;
    }

    /* Name input */
    #name-input {
        width: 40;
    }

    /* Description input */
    #description-input {
        width: 60;
    }

    /* Model select */
    #model-select {
        width: 40;
    }

    /* Temperature and Top-P inputs */
    #temp-input, #top-p-input {
        width: 15;
    }

    /* Instructions textarea */
    #instructions-area {
        height: 8;
        width: 100%;
        max-width: 80;
    }

    /* Tool checkboxes */
    #tools-container {
        padding-left: 2;
        height: auto;
    }

    .tool-row {
        height: auto;
        margin-bottom: 1;
    }

    .tool-checkbox {
        width: auto;
    }

    /* MCP approval radio */
    .approval-container {
        padding-left: 4;
        height: auto;
    }

    #approval-radio {
        layout: horizontal;
        height: auto;
    }

    #approval-radio RadioButton {
        width: auto;
        margin-right: 2;
    }

    /* Loading overlay */
    #loading-overlay {
        display: none;
        width: 100%;
        height: 100%;
        background: $background 80%;
        content-align: center middle;
        position: absolute;
    }

    #loading-overlay.visible {
        display: block;
    }

    /* Error display */
    .error-text {
        color: $error;
        padding: 1 0;
    }
    """

    def __init__(
        self,
        agent: Agent | None = None,
        project_client: ProjectClientService | None = None,
    ) -> None:
        """Initialize the edit screen.

        Args:
            agent: Agent to edit, or None for creating a new agent.
            project_client: Project client service for API operations.
        """
        super().__init__()
        self._agent = agent
        self._project_client = project_client
        self._is_new = agent is None
        self._models: list[Deployment] = []
        self._tool_configs: list[ToolConfig] = []

        # Extract existing tool configs if editing
        if agent and agent.tool_configs:
            self._tool_configs = list(agent.tool_configs)

    def _get_title(self) -> str:
        """Get screen title."""
        if self._is_new:
            return "New Agent"
        return f"Edit Agent: {self._agent.name if self._agent else ''}"

    def compose(self) -> ComposeResult:
        """Create the edit form layout."""
        yield Header()

        with Vertical(id="edit-container"):
            # Title bar
            with Horizontal(id="edit-header"):
                yield Static(self._get_title(), id="edit-title")

            # Scrollable form area
            with VerticalScroll(id="form-scroll"):
                # === Basic Info Section ===
                yield Static("Basic Information", classes="section-title")

                with Horizontal(classes="form-row"):
                    yield Label("Name:", classes="form-label")
                    yield Input(
                        value=self._agent.name if self._agent else "",
                        placeholder="Enter agent name",
                        id="name-input",
                        classes="form-field",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Description:", classes="form-label")
                    yield Input(
                        value=self._agent.description or "" if self._agent else "",
                        placeholder="Optional description",
                        id="description-input",
                        classes="form-field",
                    )

                yield Rule()

                # === Model Section ===
                yield Static("Model Configuration", classes="section-title")

                with Horizontal(classes="form-row"):
                    yield Label("Model:", classes="form-label")
                    yield Select(
                        [],
                        id="model-select",
                        prompt="Select a model",
                        classes="form-field",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Temperature:", classes="form-label")
                    yield Input(
                        value=str(self._agent.temperature or 1.0) if self._agent else "1.0",
                        placeholder="0.0 - 2.0",
                        id="temp-input",
                        type="number",
                        classes="form-field",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Top-P:", classes="form-label")
                    yield Input(
                        value=str(self._agent.top_p or 1.0) if self._agent else "1.0",
                        placeholder="0.0 - 1.0",
                        id="top-p-input",
                        type="number",
                        classes="form-field",
                    )

                yield Rule()

                # === Instructions Section ===
                yield Static("Instructions", classes="section-title")

                yield TextArea(
                    self._agent.instructions or "" if self._agent else "",
                    id="instructions-area",
                )

                yield Rule()

                # === Tools Section ===
                yield Static("Tools", classes="section-title")

                with Container(id="tools-container"):
                    # Standard tools
                    has_code_interpreter = self._has_tool("code_interpreter")
                    has_file_search = self._has_tool("file_search")

                    yield Checkbox(
                        "Code Interpreter", has_code_interpreter, id="tool-code-interpreter"
                    )
                    yield Checkbox("File Search", has_file_search, id="tool-file-search")

                    # MCP tools (if any exist)
                    mcp_tools = [t for t in self._tool_configs if t.type == "mcp"]
                    if mcp_tools:
                        yield Static("MCP Connections:", classes="form-label")
                        for i, mcp_tool in enumerate(mcp_tools):
                            label = mcp_tool.server_label or f"MCP Tool {i + 1}"
                            # Trim kb_ prefix for cleaner display
                            if label.startswith("kb_"):
                                label = label[3:]
                            yield Checkbox(
                                label,
                                True,
                                id=f"tool-mcp-{i}",
                                classes="tool-checkbox",
                            )
                            # Approval setting
                            with Container(classes="approval-container"):
                                yield Label(f"Approval for {label}:")
                                with RadioSet(id=f"approval-radio-{i}"):
                                    is_always = mcp_tool.require_approval == "always"
                                    yield RadioButton(
                                        "Always", value=is_always, id=f"approval-always-{i}"
                                    )
                                    yield RadioButton(
                                        "Never", value=not is_always, id=f"approval-never-{i}"
                                    )

            # Button bar at bottom
            with Horizontal(id="button-bar"):
                yield Button("Cancel", id="cancel-btn", classes="cancel-btn")
                yield Button("Save", id="save-btn", classes="save-btn")

        # Loading overlay
        with Container(id="loading-overlay"):
            yield Static("Loading models...", id="loading-text")

        yield Footer()

    def _has_tool(self, tool_type: str) -> bool:
        """Check if agent has a specific tool type."""
        if not self._tool_configs:
            return False
        return any(t.type == tool_type for t in self._tool_configs)

    def on_mount(self) -> None:
        """Load models on mount."""
        self._load_models()

    def _load_models(self) -> None:
        """Load available models from the project client."""
        if self._project_client:
            self.query_one("#loading-overlay").add_class("visible")
            self.run_worker(self._fetch_models, thread=True, name="fetch_models")
        else:
            # Load placeholder models for testing
            self._load_placeholder_models()

    def _fetch_models(self) -> list[Deployment]:
        """Fetch chat-completion capable models."""
        if self._project_client:
            return self._project_client.get_chat_completion_models()
        return []

    def _load_placeholder_models(self) -> None:
        """Load placeholder models for development."""
        self._models = [
            Deployment(
                name="gpt-4.1",
                model_name="gpt-4.1",
                model_version="2025-04-14",
                model_publisher="OpenAI",
                deployment_type="Global Standard",
                capacity=100,
                capabilities=["Chat Completion"],
            ),
            Deployment(
                name="gpt-4.1-mini",
                model_name="gpt-4.1-mini",
                model_version="2025-04-14",
                model_publisher="OpenAI",
                deployment_type="Global Standard",
                capacity=100,
                capabilities=["Chat Completion"],
            ),
            Deployment(
                name="gpt-4o",
                model_name="gpt-4o",
                model_version="2024-08-06",
                model_publisher="OpenAI",
                deployment_type="Global Standard",
                capacity=100,
                capabilities=["Chat Completion"],
            ),
        ]
        self._populate_model_select()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.worker.name == "fetch_models":
            self.query_one("#loading-overlay").remove_class("visible")
            if event.state == WorkerState.SUCCESS:
                self._models = event.worker.result or []
                self._populate_model_select()
            elif event.state == WorkerState.ERROR:
                self.notify(f"Failed to load models: {event.worker.error}", severity="error")
                self._load_placeholder_models()
        elif event.worker.name == "save_agent":
            self.query_one("#loading-overlay").remove_class("visible")
            if event.state == WorkerState.SUCCESS:
                self.notify("Agent saved successfully", severity="information")
                self.dismiss(event.worker.result)
            elif event.state == WorkerState.ERROR:
                self.notify(f"Failed to save agent: {event.worker.error}", severity="error")

    def _populate_model_select(self) -> None:
        """Populate the model select dropdown."""
        select = self.query_one("#model-select", Select)

        if not self._models:
            select.set_options([("No models available", None)])
            return

        options = [(m.name, m.name) for m in self._models]
        select.set_options(options)

        # Pre-select current model if editing
        if self._agent and self._agent.model:
            for model in self._models:
                if model.name == self._agent.model:
                    select.value = model.name
                    break

    def _get_form_values(self) -> dict[str, Any]:
        """Collect all form values."""
        name_input = self.query_one("#name-input", Input)
        description_input = self.query_one("#description-input", Input)
        model_select = self.query_one("#model-select", Select)
        temp_input = self.query_one("#temp-input", Input)
        top_p_input = self.query_one("#top-p-input", Input)
        instructions_area = self.query_one("#instructions-area", TextArea)

        # Parse temperature
        try:
            temperature = float(temp_input.value) if temp_input.value else 1.0
            temperature = max(0.0, min(2.0, temperature))
        except ValueError:
            temperature = 1.0

        # Parse top_p
        try:
            top_p = float(top_p_input.value) if top_p_input.value else 1.0
            top_p = max(0.0, min(1.0, top_p))
        except ValueError:
            top_p = 1.0

        # Collect tools
        tool_configs: list[ToolConfig] = []

        # Check standard tools
        code_interpreter_cb = self.query_one("#tool-code-interpreter", Checkbox)
        if code_interpreter_cb.value:
            tool_configs.append(
                ToolConfig(type="code_interpreter", display_name="Code Interpreter")
            )

        file_search_cb = self.query_one("#tool-file-search", Checkbox)
        if file_search_cb.value:
            tool_configs.append(ToolConfig(type="file_search", display_name="File Search"))

        # Collect MCP tools with approval settings
        mcp_tools = [t for t in self._tool_configs if t.type == "mcp"]
        for i, mcp_tool in enumerate(mcp_tools):
            try:
                checkbox = self.query_one(f"#tool-mcp-{i}", Checkbox)
                if checkbox.value:
                    # Check approval setting
                    approval_radio = self.query_one(f"#approval-radio-{i}", RadioSet)
                    require_approval = "always"
                    if approval_radio.pressed_index == 1:  # "Never" is index 1
                        require_approval = "never"

                    tool_configs.append(
                        ToolConfig(
                            type="mcp",
                            display_name=mcp_tool.display_name,
                            server_label=mcp_tool.server_label,
                            server_url=mcp_tool.server_url,
                            require_approval=require_approval,
                            project_connection_id=mcp_tool.project_connection_id,
                        )
                    )
            except Exception:
                # MCP checkbox might not exist
                pass

        return {
            "name": name_input.value.strip(),
            "description": description_input.value.strip() or None,
            "model": model_select.value if model_select.value != Select.BLANK else None,
            "temperature": temperature,
            "top_p": top_p,
            "instructions": instructions_area.text,
            "tool_configs": tool_configs,
        }

    def _validate_form(self, values: dict[str, Any]) -> str | None:
        """Validate form values. Returns error message or None if valid."""
        if not values["name"]:
            return "Name is required"
        if not values["model"]:
            return "Model is required"
        if not values["instructions"]:
            return "Instructions are required"
        return None

    def action_save(self) -> None:
        """Save the agent."""
        values = self._get_form_values()

        error = self._validate_form(values)
        if error:
            self.notify(error, severity="error")
            return

        if not self._project_client:
            self.notify("No project client available", severity="error")
            return

        self.query_one("#loading-overlay").add_class("visible")
        loading_text = self.query_one("#loading-text", Static)
        loading_text.update("Saving agent...")

        self.run_worker(
            lambda: self._save_agent(values),
            thread=True,
            name="save_agent",
        )

    def _save_agent(self, values: dict[str, Any]) -> Agent:
        """Save agent in background thread."""
        # These assertions are safe because we validate in action_save
        assert self._project_client is not None

        if self._is_new:
            return self._project_client.create_agent(
                name=values["name"],
                model=values["model"],
                instructions=values["instructions"],
                temperature=values["temperature"],
                top_p=values["top_p"],
                tool_configs=values["tool_configs"],
                description=values["description"],
            )
        else:
            assert self._agent is not None
            return self._project_client.update_agent(
                agent_name=self._agent.name,
                model=values["model"],
                instructions=values["instructions"],
                temperature=values["temperature"],
                top_p=values["top_p"],
                tool_configs=values["tool_configs"],
                description=values["description"],
            )

    def action_cancel(self) -> None:
        """Cancel and return to previous screen."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save-btn":
            self.action_save()
        elif event.button.id == "cancel-btn":
            self.action_cancel()
