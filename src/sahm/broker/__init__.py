"""Broker adapters. Pick one with make_client()."""

from __future__ import annotations

from ..config import Settings
from .base import BrokerClient


def make_client(settings: Settings) -> BrokerClient:
    if settings.mode == "mock":
        from .mock import MockYounitClient

        return MockYounitClient()
    if settings.mode == "live":
        from .younit import YounitClient

        return YounitClient(settings)
    raise ValueError(f"Unknown YOUNIT_MODE '{settings.mode}'. Use 'mock' or 'live'.")


__all__ = ["BrokerClient", "make_client"]
