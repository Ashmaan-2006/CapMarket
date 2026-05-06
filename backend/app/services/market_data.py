import asyncio
from dataclasses import dataclass
from datetime import date
from io import StringIO

import httpx
import pandas as pd


class MarketDataError(RuntimeError):
    pass


class MarketDataNotFoundError(MarketDataError):
    pass


class MarketDataProviderError(MarketDataError):
    pass


@dataclass(frozen=True)
class MarketDataRequest:
    symbol: str
    start_date: date | None = None
    end_date: date | None = None

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.strip().upper()


@dataclass(frozen=True)
class MarketDataResult:
    symbol: str
    source: str
    rows: pd.DataFrame
    provider_metadata: dict[str, str]


class MarketDataProvider:
    source = "provider"

    async def fetch_history(self, request: MarketDataRequest) -> MarketDataResult:
        raise NotImplementedError


class StooqProvider(MarketDataProvider):
    source = "stooq"

    def __init__(self, timeout_seconds: float = 30.0, retries: int = 2) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    async def fetch_history(self, request: MarketDataRequest) -> MarketDataResult:
        symbol = request.normalized_symbol
        stooq_symbol = f"{symbol.lower()}.us"
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"

        response_text = await self._get_with_retries(url)
        rows = self._parse_csv(symbol, response_text, request.start_date, request.end_date)
        return MarketDataResult(
            symbol=symbol,
            source=self.source,
            rows=rows,
            provider_metadata={"url": url, "provider_symbol": stooq_symbol},
        )

    async def _get_with_retries(self, url: str) -> str:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(self.retries + 1):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text
                except (httpx.HTTPError, httpx.TimeoutException) as exc:
                    last_error = exc
                    if attempt < self.retries:
                        await asyncio.sleep(0.25 * (attempt + 1))

        raise MarketDataProviderError(f"Market data provider request failed: {last_error}") from last_error

    def _parse_csv(
        self,
        symbol: str,
        response_text: str,
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        frame = pd.read_csv(StringIO(response_text))
        if frame.empty or "Date" not in frame.columns:
            raise MarketDataNotFoundError(f"No market data returned for {symbol}")

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
        if frame.empty:
            raise MarketDataNotFoundError(f"No market data returned for {symbol} in requested date range")

        frame["symbol"] = symbol
        frame["source"] = self.source
        return frame


class FixtureProvider(MarketDataProvider):
    source = "fixture"

    async def fetch_history(self, request: MarketDataRequest) -> MarketDataResult:
        symbol = request.normalized_symbol
        dates = pd.date_range(start=request.start_date or date(2024, 1, 1), end=request.end_date or date(2024, 3, 31))
        frame = pd.DataFrame(
            {
                "price_date": dates.date,
                "open": [100 + index for index in range(len(dates))],
                "high": [101 + index for index in range(len(dates))],
                "low": [99 + index for index in range(len(dates))],
                "close": [100.5 + index for index in range(len(dates))],
                "adjusted_close": [100.5 + index for index in range(len(dates))],
                "volume": [1_000_000 + index for index in range(len(dates))],
                "symbol": symbol,
                "source": self.source,
            }
        )
        return MarketDataResult(
            symbol=symbol,
            source=self.source,
            rows=frame,
            provider_metadata={"mode": "deterministic-fixture"},
        )


def get_market_data_provider(
    name: str,
    timeout_seconds: float = 30.0,
    retries: int = 2,
) -> MarketDataProvider:
    if name.lower() == "stooq":
        return StooqProvider(timeout_seconds=timeout_seconds, retries=retries)
    if name.lower() == "fixture":
        return FixtureProvider()
    raise ValueError(f"Unsupported market data provider: {name}")
