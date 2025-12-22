"""Pydantic models for Anvil configuration."""

from datetime import datetime

from pydantic import BaseModel


class FoundrySelection(BaseModel):
    """Cached Foundry resource selection."""

    subscription_id: str
    subscription_name: str
    resource_group: str
    account_name: str
    project_name: str
    project_endpoint: str
    selected_at: datetime


class AppConfig(BaseModel):
    """Application configuration."""

    last_selection: FoundrySelection | None = None
    recent_selections: list[FoundrySelection] = []
    auto_connect_last: bool = True
