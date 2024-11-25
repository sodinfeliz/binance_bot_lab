from typing import Literal

import numpy as np

from .client import BinanceClient


class GridBot:

    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        grid_number: int,
        lower_price: float,
        upper_price: float,
        qty_per_order: float,
        mode: Literal["arithmetic", "geometric"] = "arithmetic",
    ):
        self.base_asset = base_asset
        self.quote_asset = quote_asset
        self.grid_number = grid_number
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.qty_per_order = qty_per_order
        self.mode = mode.lower()

        self._tick_size = BinanceClient.get_tick_size(self.base_asset, self.quote_asset)
        self._step_size = BinanceClient.get_step_size(self.base_asset)
        self._generate_grid_levels()

    @property
    def grid_levels(self) -> list[float]:
        return self._grid_levels
    
    @property
    def tick_size(self) -> float:
        return self._tick_size
    
    @property
    def step_size(self) -> float:
        return self._step_size

    def _generate_grid_levels(self) -> None:
        """Generate the grid levels for the bot."""

        self._grid_levels = []

        if self.mode == "arithmetic":
            self.grid_interval = (self.upper_price - self.lower_price) / self.grid_number
            for i in range(self.grid_number):
                price = self.lower_price + i * self.grid_interval
                price = (price // self._tick_size) * self._tick_size  # round to the nearest tick size
                self._grid_levels.append(price)
        else:
            ratio = (self.upper_price / self.lower_price) ** (1 / self.grid_number)
            for i in range(self.grid_number):
                price = self.lower_price * ratio ** i
                price = (price // self._tick_size) * self._tick_size  # round to the nearest tick size
                self._grid_levels.append(price)

        self._grid_levels.append(self.upper_price)

    def order_count(self, price: float, align: bool = False) -> tuple[int, int]:
        if align:
            price = self.closest_grid_level(price)
        buy_count = sum(price > level for level in self._grid_levels)
        sell_count = sum(price < level for level in self._grid_levels)
        return int(buy_count), int(sell_count)
    
    def closest_grid_level(self, price: float) -> float:
        return self._grid_levels[np.argmin(np.abs(np.array(self._grid_levels) - price))]


class FuturesGridBot(GridBot):
    """Futures grid bot (Long only) for Binance"""
    
    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        grid_number: int,
        lower_price: float,
        upper_price: float,
        qty_per_order: float,
        leverage: int = 1,
    ):
        super().__init__(
            base_asset, quote_asset, grid_number, 
            lower_price, upper_price, qty_per_order
        )
        self.leverage = leverage

    def set_leverage(self, leverage: int) -> None:
        if leverage < 1 or leverage > 125:
            raise ValueError("Leverage must be between 1 and 125")
        self.leverage = leverage
    
    def liquidation_price(
        self,
        wallet_balance: float,
        maintenance_margin_rate: float,
        direction: Literal["long", "short"],
        entry_price: float,
        position_size: float,
        maintenance_amount: float = 0.0,
    ):
        side = 1 if direction == "long" else -1
        total_balance = wallet_balance + maintenance_amount
        notional_value = position_size * entry_price
        denominator = position_size * (maintenance_margin_rate - side)
        return (total_balance - notional_value * side) / denominator
