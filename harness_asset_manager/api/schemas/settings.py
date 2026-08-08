from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SettingsStorageResponse(BaseModel):
    platform: Literal["macos", "linux"]
    configDir: str
    dataDir: str
    stateDir: str
    skillsStorePath: str
    marketplaceCachePath: str
    settingsPath: str


class SettingsHarnessResponse(BaseModel):
    harness: str
    label: str
    logoKey: str | None = None
    supportEnabled: bool
    installed: bool
    managedLocation: str | None


class SettingsAutoAdoptResponse(BaseModel):
    """Whether Harness Asset Manager may repair drifted bindings without being asked."""

    agents: bool
    skills: bool
    slash_commands: bool
    mcp: bool
    hooks: bool
    permissions: bool


class SettingsResponse(BaseModel):
    storage: SettingsStorageResponse
    harnesses: list[SettingsHarnessResponse]
    autoAdopt: SettingsAutoAdoptResponse


class SetAutoAdoptRequest(BaseModel):
    enabled: bool


__all__ = [
    "SetAutoAdoptRequest",
    "SettingsAutoAdoptResponse",
    "SettingsHarnessResponse",
    "SettingsResponse",
    "SettingsStorageResponse",
]
