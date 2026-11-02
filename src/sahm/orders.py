"""Two-step order flow: preview -> explicit confirm.

The AI can never place an order in one call. preview_order validates the order,
prices it, applies the safety limits and returns a one-time token. Only
confirm_order(token) sends it to the broker, and only if trading is enabled.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from .broker.base import BrokerClient
from .config import Settings
from .models import Order, OrderRequest, OrderType


class OrderSafetyError(ValueError):
    pass


@dataclass
class PendingPreview:
    request: OrderRequest
    estimated_value_egp: float
    expires_at: float


class OrderDesk:
    def __init__(self, client: BrokerClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._pending: dict[str, PendingPreview] = {}

    def preview(self, request: OrderRequest) -> dict:
        if request.order_type == OrderType.LIMIT and request.limit_price is None:
            raise OrderSafetyError("Limit orders need a limit_price.")
        if request.order_type == OrderType.STOP and request.stop_price is None:
            raise OrderSafetyError("Stop orders need a stop_price.")

        quote = self._client.get_quote(request.symbol)
        ref_price = request.limit_price or request.stop_price or quote.last
        value = round(ref_price * request.quantity, 2)
        if value > self._settings.max_order_egp:
            raise OrderSafetyError(
                f"Order value {value:,.2f} EGP is above the {self._settings.max_order_egp:,.0f} EGP cap "
                "(YOUNIT_MAX_ORDER_EGP)."
            )

        self._sweep()
        token = secrets.token_urlsafe(8)
        self._pending[token] = PendingPreview(
            request=request,
            estimated_value_egp=value,
            expires_at=time.time() + self._settings.confirm_ttl_seconds,
        )
        return {
            "confirmation_token": token,
            "summary": f"{request.side.value.upper()} {request.quantity} {quote.symbol} "
            f"({quote.name}) as a {request.order_type.value} order",
            "last_price": quote.last,
            "estimated_value_egp": value,
            "expires_in_seconds": self._settings.confirm_ttl_seconds,
            "trading_enabled": self._settings.trading_enabled,
            "next_step": "Show this summary to the user. Call confirm_order with the token ONLY after the user explicitly says yes.",
        }

    def confirm(self, token: str) -> Order:
        if not self._settings.trading_enabled:
            raise OrderSafetyError(
                "Trading is disabled (YOUNIT_TRADING_ENABLED=false). Previews work; placing orders does not."
            )
        self._sweep()
        pending = self._pending.pop(token, None)
        if pending is None:
            raise OrderSafetyError("Unknown or expired confirmation token. Preview the order again.")
        return self._client.submit_order(pending.request)

    def _sweep(self) -> None:
        now = time.time()
        for t in [t for t, p in self._pending.items() if p.expires_at < now]:
            del self._pending[t]
