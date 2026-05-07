import pytest

from app.services.market_data import (
    MarketDataProviderError,
    StooqProvider,
    get_market_data_provider,
)


def test_stooq_provider_builds_url_with_api_key() -> None:
    provider = get_market_data_provider("stooq", stooq_api_key="test-key")

    assert isinstance(provider, StooqProvider)
    assert provider.api_key == "test-key"


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
