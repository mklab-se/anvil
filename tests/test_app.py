"""Tests for the main Anvil application."""

from datetime import datetime
from unittest.mock import patch

import pytest

from anvil.app import AnvilApp
from anvil.config import FoundrySelection
from anvil.screens.home import HomeScreen
from anvil.screens.subscription_select import SubscriptionSelectScreen
from anvil.services.auth import AuthResult, AuthStatus


@pytest.fixture
def mock_auth_authenticated():
    """Mock auth service to be authenticated."""
    with patch("anvil.app.AuthService") as mock_cls:
        mock_service = mock_cls.return_value
        mock_service.check_auth_status.return_value = AuthResult(
            status=AuthStatus.AUTHENTICATED
        )
        mock_service.is_authenticated.return_value = True
        yield mock_service


@pytest.fixture
def mock_config_with_selection(tmp_path):
    """Mock config manager with a cached selection."""
    from anvil.config import AppConfig

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

    with patch("anvil.app.ConfigManager") as mock_cls:
        mock_manager = mock_cls.return_value
        mock_manager.load.return_value = config
        mock_manager.get_last_subscription_id.return_value = selection.subscription_id
        mock_manager.get_last_account_name.return_value = selection.account_name
        mock_manager.get_last_project_name.return_value = selection.project_name
        yield mock_manager


@pytest.fixture
def mock_config_empty():
    """Mock config manager with no cached selection."""
    from anvil.config import AppConfig

    with patch("anvil.app.ConfigManager") as mock_cls:
        mock_manager = mock_cls.return_value
        mock_manager.load.return_value = AppConfig()
        mock_manager.get_last_subscription_id.return_value = None
        mock_manager.get_last_account_name.return_value = None
        mock_manager.get_last_project_name.return_value = None
        yield mock_manager


async def test_app_starts(mock_auth_authenticated, mock_config_with_selection) -> None:
    """Test that the application starts without errors."""
    app = AnvilApp()
    async with app.run_test():
        assert app.title == "Anvil"
        assert app.sub_title == "Microsoft Foundry Manager"


async def test_app_goes_to_home_with_cached_selection(
    mock_auth_authenticated, mock_config_with_selection
) -> None:
    """Test that with cached selection, app goes directly to home screen."""
    app = AnvilApp()
    async with app.run_test():
        assert isinstance(app.screen, HomeScreen)
        assert app.current_selection is not None
        assert app.current_selection.project_name == "test-project"


async def test_app_shows_selection_without_cache(
    mock_auth_authenticated, mock_config_empty
) -> None:
    """Test that without cached selection, app shows subscription selection."""
    # Need to also mock SubscriptionService since it will be called
    with patch("anvil.app.SubscriptionService"):
        app = AnvilApp()
        async with app.run_test():
            assert isinstance(app.screen, SubscriptionSelectScreen)


async def test_quit_binding_on_home(
    mock_auth_authenticated, mock_config_with_selection
) -> None:
    """Test that pressing 'q' quits the application from home screen."""
    app = AnvilApp()
    async with app.run_test() as pilot:
        # Ensure we're on home screen
        assert isinstance(app.screen, HomeScreen)
        await pilot.press("q")
        assert not app.is_running
