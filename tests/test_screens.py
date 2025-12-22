"""Tests for Anvil screens."""

import pytest

from anvil.app import AnvilApp
from anvil.screens.home import HomeScreen


@pytest.fixture
def app() -> AnvilApp:
    """Create an Anvil app instance for testing."""
    return AnvilApp()


async def test_home_screen_renders(app: AnvilApp) -> None:
    """Test that the home screen renders correctly."""
    async with app.run_test():
        assert isinstance(app.screen, HomeScreen)

        welcome = app.screen.query_one("#welcome-title")
        assert welcome is not None


async def test_home_screen_has_sidebar(app: AnvilApp) -> None:
    """Test that the home screen has a sidebar with navigation."""
    async with app.run_test():
        sidebar = app.screen.query_one("#sidebar")
        assert sidebar is not None

        nav_list = app.screen.query_one("#nav-list")
        assert nav_list is not None
