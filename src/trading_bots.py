from typing import Literal, Optional

import numpy as np

from .client import BinanceClient


class GridBot:

    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        grid_number: int,
        entry_price: float,
        lower_price: float,
        upper_price: float,
        qty_per_order: float,
        mode: Literal["arithmetic", "geometric"] = "arithmetic",
    ):
        self.base_asset = base_asset
        self.quote_asset = quote_asset
        self.grid_number = grid_number
        self.entry_price = entry_price
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

    _MAINTENANCE_MARGIN_RATE = 0.004  # ETHUSDT Perp, Notional Value < 50000 USDT
    
    def __init__(
        self,
        base_asset: str,
        quote_asset: str,
        grid_number: int,
        entry_price: float,
        lower_price: float,
        upper_price: float,
        qty_per_order: float,
        leverage: int = 1,
    ):
        super().__init__(base_asset, quote_asset, grid_number, entry_price, lower_price, upper_price, qty_per_order)
        self.leverage = leverage

    def set_leverage(self, leverage: int) -> None:
        if leverage < 1 or leverage > 125:
            raise ValueError("Leverage must be between 1 and 125")
        self.leverage = leverage

    def set_maintenance_margin_rate(self, rate: float) -> None:
        if rate < 0:
            raise ValueError("Maintenance margin rate must be non-negative")
        self._MAINTENANCE_MARGIN_RATE = rate

    def initial_position_size(self, price: Optional[float] = None) -> float:
        if price is None:
            price = self.entry_price

        _, sell_count = self.order_count(price, align=False)
        return self.qty_per_order * (sell_count - 1)
        
    def initial_margin_required(self, price: Optional[float] = None) -> float:
        if price is None:
            price = self.entry_price
        return self.initial_position_size(price) * price / self.leverage
    
    def liquidation_price(
        self,
        invested_amount: float,
        price: Optional[float] = None
    ) -> tuple[float, float]:
        """Calculate the liquidation price and unrealized PnL.

        This function simulates the worst case scenario where the price moves from the
        upper grid level to the given price. In this scenario, all the buy orders above
        the price have been filled and the price is now moving downwards.
        
        Args:
            invested_amount (float): The initial investment margin.
            price (float): The price to calculate the liquidation price and unrealized PnL at.
        
        Returns:
            (tuple[float, float]) A tuple containing the liquidation price and unrealized PnL.
        """
        if price is None:
            price = self.entry_price

        total_position_size, total_qty = 0.0, 0.0
        unrealized_pnl = 0.0

        for i in range(self.grid_number):
            grid_price = self.grid_levels[i]
            if grid_price >= price:
                total_position_size += self.qty_per_order * grid_price
                total_qty += self.qty_per_order
                unrealized_pnl -= self.qty_per_order * (grid_price - price)

        maintenance_margin = total_position_size * self._MAINTENANCE_MARGIN_RATE
        cross_margin = invested_amount + unrealized_pnl 
        multiplier = 1 - 1 / self.leverage
        liquidation_price = self.entry_price - (cross_margin - maintenance_margin) / (total_qty * multiplier)

        return liquidation_price, unrealized_pnl
    
    def deleverage_price_boundary(self, invested_amount: float) -> float:
        """Calculate the price boundary to deleverage at to avoid liquidation.
        
        Like the function `liquidation_price`, this function simulates the worst case
        scenario where the price moves from the upper grid level to the price boundary
        to avoid liquidation. The price boundary is the minimum price that the liquidation
        price is less than the current price.

        Args:
            invested_amount (float): The initial investment margin.
        
        Returns:
            (float) The price boundary to deleverage at to avoid liquidation.
        """

        price = self.grid_levels[-2]

        while True:
            liquidation_price, _ = self.liquidation_price(invested_amount, price)
            if liquidation_price < price:
                price -= self._tick_size
                continue
            else:
                break

        best_deleverage_price = price + self._tick_size
        _, unrealized_pnl = self.liquidation_price(invested_amount, best_deleverage_price)

        print(f"Unrealized PnL: {unrealized_pnl}")
        print(f"Remaining margin: {invested_amount + unrealized_pnl}")
        print(f"Best deleverage price: {best_deleverage_price}")

        return best_deleverage_price
