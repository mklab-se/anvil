# Anvil

A Terminal User Interface (TUI) for managing Microsoft Foundry projects and resources.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## Installation

### Using uvx (recommended)

Run directly without installation:

```bash
uvx anvil-tui
```

### Using uv

```bash
uv tool install anvil-tui
anvil
```

### Using pip

```bash
pip install anvil-tui
anvil
```

## Development

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

```bash
# Clone the repository
git clone https://github.com/mklab-se/anvil.git
cd anvil

# Install dependencies
uv sync --dev

# Run the application
uv run anvil

# Or use the Textual dev console for debugging
uv run textual run --dev src/anvil/app.py
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=anvil --cov-report=html

# Run a specific test file
uv run pytest tests/test_app.py

# Run a specific test
uv run pytest tests/test_app.py::test_app_starts
```

### Linting and Formatting

```bash
# Check code style
uv run ruff check src tests

# Auto-fix issues
uv run ruff check --fix src tests

# Format code
uv run ruff format src tests

# Type checking
uv run mypy src
```

## Project Structure

```
anvil/
├── src/anvil/
│   ├── app.py          # Main application entry point
│   ├── screens/        # TUI screens (pages)
│   ├── widgets/        # Custom Textual widgets
│   ├── services/       # API and backend services
│   └── styles/         # TCSS stylesheets
├── tests/              # Test suite
└── pyproject.toml      # Project configuration
```

## License

MIT
