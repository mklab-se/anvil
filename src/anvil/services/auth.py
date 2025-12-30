"""Azure authentication service for Anvil."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from azure.core.credentials import TokenCredential
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import AzureCliCredential, InteractiveBrowserCredential

from anvil.services.exceptions import NotAuthenticated
from anvil.services.ssl_config import format_ssl_error_message

if TYPE_CHECKING:
    pass


class AuthStatus(Enum):
    """Authentication status."""

    AUTHENTICATED = "authenticated"
    NOT_AUTHENTICATED = "not_authenticated"
    AUTH_FAILED = "auth_failed"


@dataclass
class AuthResult:
    """Result of authentication check or login attempt."""

    status: AuthStatus
    error_message: str | None = None


class AuthService:
    """Handles Azure authentication with credential chain."""

    MANAGEMENT_SCOPE = "https://management.azure.com/.default"

    def __init__(self) -> None:
        """Initialize the auth service."""
        self._credential: TokenCredential | None = None

    def check_auth_status(self) -> AuthResult:
        """Check if user is already authenticated via CLI.

        Tries AzureCliCredential first (user may have run `az login`).

        Returns:
            AuthResult with current authentication status.
        """
        try:
            cli_credential = AzureCliCredential()
            # Try to get a token to verify authentication
            cli_credential.get_token(self.MANAGEMENT_SCOPE)
            self._credential = cli_credential
            return AuthResult(status=AuthStatus.AUTHENTICATED)
        except ClientAuthenticationError:
            return AuthResult(
                status=AuthStatus.NOT_AUTHENTICATED,
                error_message="Not logged in. Run 'az login' or use browser login.",
            )
        except Exception as e:
            # Format SSL errors with helpful guidance
            error_msg = format_ssl_error_message(e)
            return AuthResult(
                status=AuthStatus.NOT_AUTHENTICATED,
                error_message=error_msg,
            )

    def login(self) -> AuthResult:
        """Initiate browser-based login flow.

        Uses InteractiveBrowserCredential to open browser for authentication.

        Returns:
            AuthResult with login status.
        """
        try:
            browser_credential = InteractiveBrowserCredential()
            # Try to get a token to trigger browser login
            browser_credential.get_token(self.MANAGEMENT_SCOPE)
            self._credential = browser_credential
            return AuthResult(status=AuthStatus.AUTHENTICATED)
        except ClientAuthenticationError as e:
            return AuthResult(
                status=AuthStatus.AUTH_FAILED,
                error_message=f"Authentication failed: {e}",
            )
        except Exception as e:
            # Format SSL errors with helpful guidance
            error_msg = format_ssl_error_message(e)
            return AuthResult(
                status=AuthStatus.AUTH_FAILED,
                error_message=error_msg,
            )

    def get_credential(self) -> TokenCredential:
        """Return the authenticated credential for SDK clients.

        Returns:
            TokenCredential for use with Azure SDKs.

        Raises:
            NotAuthenticated: If not authenticated.
        """
        if not self._credential:
            raise NotAuthenticated("Must authenticate first")
        return self._credential

    def is_authenticated(self) -> bool:
        """Check if currently authenticated.

        Returns:
            True if authenticated, False otherwise.
        """
        return self._credential is not None

    def logout(self) -> None:
        """Clear cached credentials."""
        self._credential = None
