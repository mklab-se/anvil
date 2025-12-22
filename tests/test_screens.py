"""Tests for Anvil screens."""

from datetime import datetime
from unittest.mock import patch

import pytest

from anvil.app import AnvilApp
from anvil.config import AppConfig, FoundrySelection
from anvil.screens.home import HomeScreen
from anvil.services.auth import AuthResult, AuthStatus


@pytest.fixture
def mock_auth_and_config():
    """Mock both auth and config for testing home screen."""
    selection = FoundrySelection(
        subscription_id="test-sub-id",
        subscription_name="Test Subscription",
        resource_group="test-rg",
        account_name="test-account",
        project_name="test-project",
        project_endpoint="https://test.endpoint",
        selected_at=datetime.now(),
    )
    config = AppConfig(last_selection=selection, auto_connect_last=True)

    with (
        patch("anvil.app.AuthService") as mock_auth_cls,
        patch("anvil.app.ConfigManager") as mock_config_cls,
    ):
        mock_auth = mock_auth_cls.return_value
        mock_auth.check_auth_status.return_value = AuthResult(status=AuthStatus.AUTHENTICATED)
        mock_auth.is_authenticated.return_value = True

        mock_config = mock_config_cls.return_value
        mock_config.load.return_value = config
        mock_config.get_last_subscription_id.return_value = selection.subscription_id
        mock_config.get_last_account_name.return_value = selection.account_name
        mock_config.get_last_project_name.return_value = selection.project_name

        yield {"auth": mock_auth, "config": mock_config, "selection": selection}


async def test_home_screen_renders(mock_auth_and_config) -> None:
    """Test that the home screen renders correctly."""
    app = AnvilApp()
    async with app.run_test():
        assert isinstance(app.screen, HomeScreen)

        welcome = app.screen.query_one("#welcome-title")
        assert welcome is not None


async def test_home_screen_has_sidebar(mock_auth_and_config) -> None:
    """Test that the home screen has a sidebar with navigation."""
    app = AnvilApp()
    async with app.run_test():
        sidebar = app.screen.query_one("#sidebar")
        assert sidebar is not None

        nav_list = app.screen.query_one("#nav-list")
        assert nav_list is not None


async def test_home_screen_shows_project_info(mock_auth_and_config) -> None:
    """Test that the home screen displays current project info."""
    app = AnvilApp()
    async with app.run_test():
        connection_info = app.screen.query_one("#connection-info")
        assert connection_info is not None

        project_name = app.screen.query_one("#project-name")
        assert project_name is not None
