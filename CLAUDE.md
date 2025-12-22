# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Anvil is a Terminal User Interface (TUI) for managing Microsoft Foundry projects and resources. Built with Python and Textual framework.

- **Package name**: `anvil-tui` (on PyPI)
- **Commands**: `anvil` or `anvil-tui`
- **Install**: `uvx anvil-tui` or `uv tool install anvil-tui`

## Screenshots

Anvil automatically saves screenshots as SVG files in the user's Downloads folder when taken from within the app. The filename format is `Anvil_<timestamp>.svg`, for example `Anvil_2025-12-22T22_49_35_707419.svg`.

If the user refers to a screenshot but none is pasted in the prompt, check `~/Downloads/` for the latest `Anvil_*.svg` file.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run the application (development)
uv run anvil

# Run with Textual dev console (shows CSS and widget tree)
uv run textual run --dev src/anvil/app.py

# Run all tests
uv run pytest

# Run single test file
uv run pytest tests/test_app.py

# Run single test
uv run pytest tests/test_app.py::test_app_starts -v

# Lint and format
uv run ruff check src tests
uv run ruff check --fix src tests
uv run ruff format src tests

# Type check
uv run mypy src
```

## Development Workflow

Before starting any implementation, run `uv run pytest && uv run ruff check src tests && uv run mypy src` to ensure the codebase is in a working state. After completing changes, run the same commands to verify nothing broke. This keeps the system stable and gives you a solid foundation.

### Dependencies Philosophy

Always use the latest Python libraries in this project. The core purpose of Anvil is to provide an up-to-date user interface with the latest APIs, even when the official Microsoft portal doesn't yet support them. Don't hold back on using new library versions or features.

## Architecture

### Textual Framework Pattern

This app uses Textual's screen-based architecture:

- **App** (`app.py`): Root application class, manages screen stack and global bindings
- **Screens** (`screens/`): Full-page views pushed onto screen stack via `app.push_screen()`
- **Widgets** (`widgets/`): Reusable UI components composed within screens
- **Styles** (`styles/`): TCSS files (Textual's CSS variant) for styling

### Key Textual Concepts

- `compose()` method yields child widgets using `yield` syntax
- Containers (`Horizontal`, `Vertical`, `Container`) for layout
- CSS-like selectors in `.tcss` files for styling
- `@on(Event)` decorator or `on_*` methods for event handling
- `self.query_one("#id")` to find widgets by ID
- Async by default - screens and widgets can use `async` methods

### Services Layer

`services/` contains API clients and business logic for communicating with Microsoft Foundry APIs. Keep UI logic in screens/widgets, API logic in services.

### Testing

Tests use `pytest-asyncio` with Textual's test framework:

```python
async def test_example(app: AnvilApp) -> None:
    async with app.run_test() as pilot:
        await pilot.press("enter")
        assert app.query_one("#widget-id")
```

The `pilot` object simulates user interaction (clicks, key presses). Use `app.query_one()` to assert widget state.

#### Coverage Goals

| Component | Target | Priority |
|-----------|--------|----------|
| **Overall** | 75% | - |
| **Services** (`services/`) | 85% | High - API/SDK parsing bugs are hard to debug in production |
| **Screens** (`screens/`) | 65% | Medium - UI handlers are harder to test |
| **Widgets** (`widgets/`) | 75% | Medium - Reusable components |

#### Testing Best Practices

1. **Always add tests for new features and bug fixes** - When implementing a new feature or fixing a bug, consider what tests would catch regressions. This is mandatory, not optional.
2. **Always mock external APIs** - Use `unittest.mock` to simulate SDK responses with the real data structure
3. **Test the actual SDK response format** - When integrating with Azure SDKs, first inspect what the API actually returns (nested structures, dict-like objects, etc.) and create mock fixtures that match
4. **Test edge cases** - Empty lists, None values, missing fields
5. **Test race conditions** - When async workers or background tasks are involved, test that data doesn't leak between views
6. **Test formatting functions** - Sidebar previews, table displays, truncation logic

Example of mocking Azure SDK responses:

```python
def _create_mock_agent(self, agent_id: str, name: str, model: str) -> MagicMock:
    """Create mock with REAL Azure SDK structure."""
    mock = MagicMock()
    mock.id = agent_id
    mock.name = name
    mock.versions = {
        "latest": {
            "definition": {"model": model, "instructions": "..."}
        }
    }
    return mock
```

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Runs on push/PR to main - lint, type check, test on Python 3.11-3.13
- **Publish** (`.github/workflows/publish.yml`): Publishes to PyPI on GitHub release using trusted publishing

## Releasing

To release a new version:

1. Update version in `pyproject.toml` and `src/anvil/__init__.py`
2. Commit and push to main
3. Create a GitHub release: `gh release create vX.Y.Z --title "vX.Y.Z" --notes "Release notes"`
4. The publish workflow automatically uploads to PyPI
