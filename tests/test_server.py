"""End-to-end: start the real server over stdio and call tools like an MCP client would."""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {
    "get_account", "get_positions", "list_symbols", "get_quote", "get_price_history",
    "get_orders", "list_strategies", "backtest_strategy", "preview_order",
    "confirm_order", "cancel_order",
}


async def _run():
    env = {**os.environ, "YOUNIT_MODE": "mock", "YOUNIT_TRADING_ENABLED": "false"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "sahm.server"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
            quote = await s.call_tool("get_quote", {"symbol": "comi"})
            bt = await s.call_tool("backtest_strategy", {"symbol": "TMGH", "strategy": "sma_cross"})
            prev = await s.call_tool("preview_order", {"symbol": "FWRY", "side": "buy", "quantity": 5})
            token = json.loads(prev.content[0].text)["confirmation_token"]
            conf = await s.call_tool("confirm_order", {"confirmation_token": token})
            return names, quote, bt, conf


def test_server_end_to_end():
    names, quote, bt, conf = asyncio.run(_run())
    assert EXPECTED <= names
    assert json.loads(quote.content[0].text)["symbol"] == "COMI"
    assert "total_return_pct" in json.loads(bt.content[0].text)
    assert conf.isError and "disabled" in conf.content[0].text
