from datetime import date
from io import StringIO

import httpx
import pandas as pd


class MarketDataProvider:
    source = "provider"

    async def fetch_history(self, symbol: str, start_date: date | None, end_date: date | None) -> pd.DataFrame:
        raise NotImplementedError


class StooqProvider(MarketDataProvider):
    source = "stooq"

    async def fetch_history(self, symbol: str, start_date: date | None, end_date: date | None) -> pd.DataFrame:
        stooq_symbol = f"{symbol.lower()}.us"
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()

        frame = pd.read_csv(StringIO(response.text))
        if frame.empty or "Date" not in frame.columns:
            raise ValueError(f"No market data returned for {symbol}")

        frame = frame.rename(
            columns={
                "Date": "price_date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        frame["adjusted_close"] = frame["close"]
        frame["price_date"] = pd.to_datetime(frame["price_date"]).dt.date
        if start_date:
            frame = frame[frame["price_date"] >= start_date]
        if end_date:
            frame = frame[frame["price_date"] <= end_date]
        frame["symbol"] = symbol.upper()
        frame["source"] = self.source
        return frame


def get_market_data_provider(name: str) -> MarketDataProvider:
    if name.lower() == "stooq":
        return StooqProvider()
    raise ValueError(f"Unsupported market data provider: {name}")

