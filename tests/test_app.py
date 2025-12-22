"""Tests for the main Anvil application."""

import pytest

from anvil.app import AnvilApp
from anvil.screens.home import HomeScreen


@pytest.fixture
def app() -> AnvilApp:
    """Create an Anvil app instance for testing."""
    return AnvilApp()


async def test_app_starts(app: AnvilApp) -> None:
    """Test that the application starts without errors."""
    async with app.run_test():
        assert app.title == "Anvil"
        assert app.sub_title == "Microsoft Foundry Manager"


async def test_app_has_home_screen(app: AnvilApp) -> None:
    """Test that the home screen is pushed on startup."""
    async with app.run_test():
        assert isinstance(app.screen, HomeScreen)


async def test_quit_binding(app: AnvilApp) -> None:
    """Test that pressing 'q' quits the application."""
    async with app.run_test() as pilot:
        await pilot.press("q")
        assert not app.is_running
