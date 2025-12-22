"""Configuration file management for Anvil."""

import json
from pathlib import Path

from anvil.config.models import AppConfig, FoundrySelection


class ConfigManager:
    """Manages ~/.config/anvil/ directory and config.json."""

    MAX_RECENT_SELECTIONS = 5

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize config manager.

        Args:
            config_dir: Override config directory (for testing).
        """
        self._config_dir = config_dir or (Path.home() / ".config" / "anvil")
        self._config_file = self._config_dir / "config.json"

    @property
    def config_dir(self) -> Path:
        """Return the config directory path."""
        return self._config_dir

    @property
    def config_file(self) -> Path:
        """Return the config file path."""
        return self._config_file

    def _ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppConfig:
        """Load configuration from disk.

        Returns:
            AppConfig with loaded values or defaults.
        """
        if not self._config_file.exists():
            return AppConfig()

        try:
            data = json.loads(self._config_file.read_text())
            return AppConfig.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            # Invalid config file, return defaults
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        """Save configuration to disk.

        Args:
            config: Configuration to save.
        """
        self._ensure_config_dir()
        data = config.model_dump(mode="json")
        self._config_file.write_text(json.dumps(data, indent=2, default=str))

    def update_selection(self, selection: FoundrySelection) -> None:
        """Update the last selection and add to recent list.

        Args:
            selection: The new selection to save.
        """
        config = self.load()

        # Update last selection
        config.last_selection = selection

        # Add to recent selections (avoid duplicates by project endpoint)
        recent = [
            s
            for s in config.recent_selections
            if s.project_endpoint != selection.project_endpoint
        ]
        recent.insert(0, selection)
        config.recent_selections = recent[: self.MAX_RECENT_SELECTIONS]

        self.save(config)

    def clear(self) -> None:
        """Clear all configuration."""
        if self._config_file.exists():
            self._config_file.unlink()

    def get_last_subscription_id(self) -> str | None:
        """Get the last used subscription ID."""
        config = self.load()
        return config.last_selection.subscription_id if config.last_selection else None

    def get_last_account_name(self) -> str | None:
        """Get the last used Foundry account name."""
        config = self.load()
        return config.last_selection.account_name if config.last_selection else None

    def get_last_project_name(self) -> str | None:
        """Get the last used project name."""
        config = self.load()
        return config.last_selection.project_name if config.last_selection else None
