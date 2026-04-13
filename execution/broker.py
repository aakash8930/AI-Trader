# execution/broker.py

from datetime import datetime
from typing import Optional

import ccxt

from execution.position import Position


class PaperBroker:
    """
    Simulates order execution (paper trading).
    """

    def __init__(self):
        self.position: Optional[Position] = None

    def open_position(self, side: str, price: float, qty: float, symbol: str | None = None) -> Position:
        self.position = Position(
            side=side,
            entry_price=price,
            qty=qty,
            entry_time=datetime.utcnow(),
        )
        return self.position

    def close_position(self, price: float, symbol: str | None = None) -> float:
        if self.position is None:
            return 0.0

        pnl = self.position.pnl(price)
        self.position = None
        return pnl


class ShadowBroker(PaperBroker):
    """
    Shadow trading broker.
    Executes ZERO real orders.
    Mirrors live behavior for validation.
    """

    def __init__(self):
        super().__init__()

    def open_position(self, side: str, price: float, qty: float, symbol: str | None = None) -> Position:
        print(f"[SHADOW] OPEN {side} {symbol} qty={qty:.6f} @ {price:.2f}")
        return super().open_position(side, price, qty, symbol)

    def close_position(self, price: float, symbol: str | None = None) -> float:
        pnl = super().close_position(price, symbol)
        print(f"[SHADOW] CLOSE {symbol} pnl={pnl:.4f}")
        return pnl


class LiveBroker:
    """
    Executes real market orders via ccxt (spot only, LONG only).
    """

    def __init__(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
    ):
        if exchange_name != "binance":
            raise ValueError(f"Unsupported exchange: {exchange_name}")

        self.exchange = ccxt.binance(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )

        if testnet and hasattr(self.exchange, "set_sandbox_mode"):
            self.exchange.set_sandbox_mode(True)

        self.exchange.load_markets()
        self.position: Optional[Position] = None

    def get_balance_usdt(self) -> float:
        balance = self.exchange.fetch_balance()
        return float(
            balance.get("free", {}).get("USDT")
            or balance.get("total", {}).get("USDT")
            or 0.0
        )

    def _normalize_qty(self, symbol: str, qty: float) -> float:
        qty = float(self.exchange.amount_to_precision(symbol, qty))
        min_amount = self.exchange.market(symbol).get("limits", {}).get("amount", {}).get("min")

        if min_amount and qty < float(min_amount):
            raise ValueError(f"Order qty too small for {symbol}")

        return qty

    def _validate_notional(self, symbol: str, qty: float, price: float) -> None:
        min_cost = self.exchange.market(symbol).get("limits", {}).get("cost", {}).get("min")
        if min_cost and qty * price < float(min_cost):
            raise ValueError(f"Order notional too small for {symbol}")

    def open_position(self, side: str, price: float, qty: float, symbol: str) -> Position:
        if self.position:
            raise RuntimeError("Position already open")

        if side != "LONG":
            raise ValueError("Live spot broker supports LONG only")

        qty = self._normalize_qty(symbol, qty)
        self._validate_notional(symbol, qty, price)

        order = self.exchange.create_order(symbol, "market", "buy", qty)
        fill_price = float(order.get("average") or price)
        filled_qty = float(order.get("filled") or qty)

        if filled_qty <= 0:
            raise RuntimeError("Buy order not filled")

        self.position = Position(
            side=side,
            entry_price=fill_price,
            qty=filled_qty,
            entry_time=datetime.utcnow(),
        )
        return self.position

    def close_position(self, price: float, symbol: str) -> float:
        if not self.position:
            return 0.0

        qty = self._normalize_qty(symbol, self.position.qty)
        order = self.exchange.create_order(symbol, "market", "sell", qty)
        exit_price = float(order.get("average") or price)

        pnl = self.position.pnl(exit_price)
        self.position = None
        return pnl