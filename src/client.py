import os

from binance.client import Client  # type: ignore


class BinanceClient:

    _CLIENT = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"))
    _EXCHANGE_INFO: dict | None = None

    @classmethod
    def get_client(cls) -> Client:
        return cls._CLIENT
    
    @classmethod
    def get_exchange_info(cls) -> dict:
        if cls._EXCHANGE_INFO is None:
            cls._EXCHANGE_INFO = cls._CLIENT.get_exchange_info()
        return cls._EXCHANGE_INFO
    
    @classmethod
    def get_tick_size(cls, base_asset: str, quote_asset: str) -> float:
        """Get the tick size for a given base and quote asset."""
        if cls._EXCHANGE_INFO is None:
            cls._EXCHANGE_INFO = cls._CLIENT.get_exchange_info()

        base_asset = base_asset.upper()
        quote_asset = quote_asset.upper()

        for symbol_info in cls._EXCHANGE_INFO["symbols"]:
            if symbol_info["baseAsset"] == base_asset and symbol_info["quoteAsset"] == quote_asset:
                for filter in symbol_info["filters"]:
                    if filter["filterType"] == "PRICE_FILTER":
                        return float(filter["tickSize"])
        else:
            raise ValueError(f"No tick size found for {base_asset}{quote_asset}")


    @classmethod
    def get_step_size(cls, base_asset: str) -> float:
        """Get the step size for a given base asset.
        
        Step size is the minimum increment for a given asset, 
        which is independent of the quote asset.

        For example, the step size for ETH is 0.0001, 
        which means the minimum increment for ETH is 0.0001.

        Args:
            base_asset: The base asset to get the step size for.

        Returns:
            The step size for the given base asset.
        """
        base_asset = base_asset.upper()
        if cls._EXCHANGE_INFO is None:
            cls._EXCHANGE_INFO = cls._CLIENT.get_exchange_info()

        for symbol_info in cls._EXCHANGE_INFO["symbols"]:
            if symbol_info["baseAsset"] == base_asset:
                for filter in symbol_info["filters"]:
                    if filter["filterType"] == "LOT_SIZE":
                        return float(filter["stepSize"])
        else:
            raise ValueError(f"No step size found for {base_asset}")
