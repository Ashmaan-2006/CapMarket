from datetime import date

import pytest

from app.services.market_data import (
    AlphaVantageProvider,
    MarketDataProviderError,
    StooqProvider,
    get_market_data_provider,
)


def test_stooq_provider_builds_url_with_api_key() -> None:
    provider = get_market_data_provider("stooq", stooq_api_key="test-key")

    assert isinstance(provider, StooqProvider)
    assert provider.api_key == "test-key"


def test_stooq_provider_defaults_plain_symbols_to_us_listing() -> None:
    provider = StooqProvider()

    assert provider._provider_symbol("AAPL") == "aapl.us"


def test_stooq_provider_preserves_provider_specific_suffixes() -> None:
    provider = StooqProvider()

    assert provider._provider_symbol("SHOP.TO") == "shop.to"


def test_stooq_provider_rejects_api_key_instruction_response() -> None:
    provider = StooqProvider()

    with pytest.raises(MarketDataProviderError, match="requires an API key"):
        provider._parse_csv(
            symbol="AAPL",
            response_text="Get your apikey:\nOpen https://stooq.com/q/d/?s=aapl.us&get_apikey",
            start_date=None,
            end_date=None,
        )


def test_stooq_provider_wraps_non_csv_response() -> None:
    provider = StooqProvider()

    with pytest.raises(MarketDataProviderError, match="non-CSV"):
        provider._parse_csv(
            symbol="AAPL",
            response_text="not-csv\none-field\nstill-one-field\nnow,two-fields",
            start_date=None,
            end_date=None,
        )


def test_alpha_vantage_provider_requires_api_key() -> None:
    provider = get_market_data_provider("alpha_vantage", alpha_vantage_api_key="av-key")

    assert isinstance(provider, AlphaVantageProvider)
    assert provider.api_key == "av-key"


def test_alpha_vantage_provider_parses_daily_payload() -> None:
    provider = AlphaVantageProvider(api_key="av-key")

    frame = provider._parse_payload(
        symbol="TSLA",
        payload={
            "Time Series (Daily)": {
                "2024-01-03": {
                    "1. open": "250.00",
                    "2. high": "255.50",
                    "3. low": "248.25",
                    "4. close": "253.00",
                    "5. volume": "120000000",
                },
                "2024-01-02": {
                    "1. open": "245.00",
                    "2. high": "251.00",
                    "3. low": "243.00",
                    "4. close": "250.00",
                    "5. volume": "100000000",
                },
            }
        },
        start_date=None,
        end_date=None,
    )

    assert list(frame["price_date"]) == [
        date(2024, 1, 2),
        date(2024, 1, 3),
    ]
    assert frame.iloc[0]["symbol"] == "TSLA"
    assert frame.iloc[0]["source"] == "alpha_vantage"
    assert frame.iloc[1]["close"] == 253.0
    assert frame.iloc[1]["volume"] == 120000000


def test_alpha_vantage_provider_surfaces_provider_errors() -> None:
    provider = AlphaVantageProvider(api_key="av-key")

    with pytest.raises(MarketDataProviderError, match="Alpha Vantage error"):
        provider._parse_payload(
            symbol="BAD",
            payload={"Error Message": "Invalid API call."},
            start_date=None,
            end_date=None,
        )
