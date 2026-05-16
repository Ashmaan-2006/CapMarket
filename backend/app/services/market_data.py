import asyncio
from dataclasses import dataclass
from datetime import date
from io import StringIO
from urllib.parse import urlencode

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

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        retries: int = 2,
        api_key: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.api_key = api_key

    def _provider_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().lower()
        if "." in normalized:
            return normalized
        return f"{normalized}.us"

    async def fetch_history(self, request: MarketDataRequest) -> MarketDataResult:
        symbol = request.normalized_symbol
        stooq_symbol = self._provider_symbol(symbol)
        params = {"s": stooq_symbol, "i": "d"}
        if self.api_key:
            params["apikey"] = self.api_key
        url = f"https://stooq.com/q/d/l/?{urlencode(params)}"

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
        if "Get your apikey" in response_text:
            raise MarketDataProviderError(
                "Stooq now requires an API key for CSV downloads. Set STOOQ_API_KEY "
                "or use MARKET_DATA_PROVIDER=fixture for local demos."
            )

        try:
            frame = pd.read_csv(StringIO(response_text))
        except pd.errors.ParserError as exc:
            raise MarketDataProviderError("Market data provider returned non-CSV content") from exc
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


class AlphaVantageProvider(MarketDataProvider):
    source = "alpha_vantage"
    base_url = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None,
        timeout_seconds: float = 30.0,
        retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    async def fetch_history(self, request: MarketDataRequest) -> MarketDataResult:
        if not self.api_key:
            raise MarketDataProviderError("Alpha Vantage requires ALPHA_VANTAGE_API_KEY")

        symbol = request.normalized_symbol
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": self.api_key,
        }
        payload = await self._get_json_with_retries(params)
        rows = self._parse_payload(symbol, payload, request.start_date, request.end_date)
        return MarketDataResult(
            symbol=symbol,
            source=self.source,
            rows=rows,
            provider_metadata={"provider_symbol": symbol, "function": "TIME_SERIES_DAILY"},
        )

    async def _get_json_with_retries(self, params: dict[str, str]) -> dict[str, object]:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(self.retries + 1):
                try:
                    response = await client.get(self.base_url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise MarketDataProviderError("Alpha Vantage returned an unexpected response")
                    return payload
                except (httpx.HTTPError, httpx.TimeoutException, ValueError, MarketDataProviderError) as exc:
                    last_error = exc
                    if attempt < self.retries:
                        await asyncio.sleep(0.25 * (attempt + 1))

        raise MarketDataProviderError(f"Alpha Vantage request failed: {last_error}") from last_error

    def _parse_payload(
        self,
        symbol: str,
        payload: dict[str, object],
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        provider_error = payload.get("Error Message") or payload.get("Note") or payload.get("Information")
        if provider_error:
            raise MarketDataProviderError(f"Alpha Vantage error: {provider_error}")

        time_series = payload.get("Time Series (Daily)")
        if not isinstance(time_series, dict) or not time_series:
            raise MarketDataNotFoundError(f"No market data returned for {symbol}")

        records: list[dict[str, object]] = []
        for date_text, values in time_series.items():
            if not isinstance(values, dict):
                continue
            records.append(
                {
                    "price_date": date_text,
                    "open": values.get("1. open"),
                    "high": values.get("2. high"),
                    "low": values.get("3. low"),
                    "close": values.get("4. close"),
                    "adjusted_close": values.get("4. close"),
                    "volume": values.get("5. volume"),
                    "symbol": symbol,
                    "source": self.source,
                }
            )

        frame = pd.DataFrame.from_records(records)
        if frame.empty:
            raise MarketDataNotFoundError(f"No market data returned for {symbol}")

        frame["price_date"] = pd.to_datetime(frame["price_date"]).dt.date
        for column in ["open", "high", "low", "close", "adjusted_close", "volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["open", "high", "low", "close", "adjusted_close", "volume"])
        frame = frame.sort_values("price_date")
        if start_date:
            frame = frame[frame["price_date"] >= start_date]
        if end_date:
            frame = frame[frame["price_date"] <= end_date]
        if frame.empty:
            raise MarketDataNotFoundError(f"No market data returned for {symbol} in requested date range")

        frame["volume"] = frame["volume"].astype("int64")
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
    stooq_api_key: str | None = None,
    alpha_vantage_api_key: str | None = None,
) -> MarketDataProvider:
    if name.lower() == "stooq":
        return StooqProvider(
            timeout_seconds=timeout_seconds,
            retries=retries,
            api_key=stooq_api_key,
        )
    if name.lower() == "fixture":
        return FixtureProvider()
    if name.lower() in {"alpha_vantage", "alphavantage"}:
        return AlphaVantageProvider(
            api_key=alpha_vantage_api_key,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
    raise ValueError(f"Unsupported market data provider: {name}")
