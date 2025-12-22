"""Custom exceptions for Anvil services."""


class AnvilError(Exception):
    """Base exception for Anvil."""

    pass


class NotAuthenticated(AnvilError):
    """User is not authenticated."""

    pass


class AuthenticationFailed(AnvilError):
    """Authentication attempt failed."""

    pass


class NetworkError(AnvilError):
    """Network connectivity issue."""

    pass


class ResourceNotFound(AnvilError):
    """Azure resource not found."""

    pass
