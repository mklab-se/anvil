"""Azure Subscriptions service for Anvil."""

from dataclasses import dataclass

from azure.core.credentials import TokenCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.mgmt.resource.subscriptions import SubscriptionClient

from anvil.services.exceptions import NetworkError, NotAuthenticated


@dataclass
class Subscription:
    """Azure subscription information."""

    id: str
    subscription_id: str
    display_name: str
    state: str


class SubscriptionService:
    """Lists and filters Azure subscriptions."""

    def __init__(self, credential: TokenCredential) -> None:
        """Initialize the subscription service.

        Args:
            credential: Azure credential for authentication.
        """
        self._credential = credential

    def list_subscriptions(self) -> list[Subscription]:
        """List all subscriptions user has access to.

        Returns:
            List of enabled subscriptions.

        Raises:
            NotAuthenticated: If credential is invalid.
            NetworkError: If network request fails.
        """
        try:
            client = SubscriptionClient(self._credential)
            subscriptions: list[Subscription] = []

            for sub in client.subscriptions.list():
                if sub.state and sub.state.lower() == "enabled":
                    subscriptions.append(
                        Subscription(
                            id=sub.id or "",
                            subscription_id=sub.subscription_id or "",
                            display_name=sub.display_name or "",
                            state=sub.state or "",
                        )
                    )

            return subscriptions
        except ClientAuthenticationError as e:
            raise NotAuthenticated(str(e)) from e
        except HttpResponseError as e:
            raise NetworkError(f"Failed to list subscriptions: {e}") from e
