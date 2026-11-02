"""Settings loaded from environment variables (or a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mode: str = "mock"
    real_money: bool = False  # live mode only: False = Younit simulation (paper) environment
    watchlist: tuple[str, ...] = ("COMI", "HRHO", "TMGH", "EAST", "SWDY", "FWRY", "ETEL", "ABUK")
    trading_enabled: bool = False
    max_order_egp: float = 5000.0
    confirm_ttl_seconds: int = 120

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        wl = os.getenv("YOUNIT_WATCHLIST", "")
        return cls(
            mode=os.getenv("YOUNIT_MODE", "mock").strip().lower(),
            real_money=_bool(os.getenv("YOUNIT_REAL_MONEY"), False),
            watchlist=tuple(s.strip().upper() for s in wl.split(",") if s.strip()) or cls.watchlist,
            trading_enabled=_bool(os.getenv("YOUNIT_TRADING_ENABLED"), False),
            max_order_egp=float(os.getenv("YOUNIT_MAX_ORDER_EGP", "5000")),
            confirm_ttl_seconds=int(os.getenv("YOUNIT_CONFIRM_TTL_SECONDS", "120")),
        )
