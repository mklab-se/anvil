# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Anvil is a Terminal User Interface (TUI) for managing Microsoft Foundry projects and resources. Built with Python and Textual framework.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run the application
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

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Runs on push/PR to main - lint, type check, test on Python 3.11-3.13
- **Publish** (`.github/workflows/publish.yml`): Publishes to PyPI on GitHub release using trusted publishing
