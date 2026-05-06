import pandas as pd


REQUIRED_PRICE_COLUMNS = {
    "price_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "source",
}

OPTIONAL_PRICE_COLUMNS = {"adjusted_close"}


class PriceTransformError(ValueError):
    pass


def clean_price_history(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_PRICE_COLUMNS.difference(frame.columns)
    if missing:
        raise PriceTransformError(f"Missing required price columns: {sorted(missing)}")

    cleaned = frame.copy()
    if "adjusted_close" not in cleaned.columns:
        cleaned["adjusted_close"] = cleaned["close"]

    cleaned["symbol"] = cleaned["symbol"].astype(str).str.strip().str.upper()
    cleaned["source"] = cleaned["source"].astype(str).str.strip().str.lower()
    cleaned["price_date"] = pd.to_datetime(cleaned["price_date"], errors="coerce").dt.date

    for column in ["open", "high", "low", "close", "adjusted_close"]:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    cleaned["volume"] = pd.to_numeric(cleaned["volume"], errors="coerce")
    cleaned = cleaned.dropna(
        subset=["symbol", "source", "price_date", "open", "high", "low", "close", "volume"]
    )
    cleaned["volume"] = cleaned["volume"].astype("int64")

    cleaned = cleaned[
        (cleaned["symbol"] != "")
        & (cleaned["source"] != "")
        & (cleaned["open"] >= 0)
        & (cleaned["high"] >= 0)
        & (cleaned["low"] >= 0)
        & (cleaned["close"] >= 0)
        & (cleaned["high"] >= cleaned["low"])
        & (cleaned["volume"] >= 0)
    ]

    cleaned = cleaned.drop_duplicates(
        subset=["symbol", "price_date", "source"],
        keep="last",
    )
    cleaned = cleaned.sort_values(["symbol", "price_date"]).reset_index(drop=True)

    return cleaned[
        [
            "price_date",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
            "symbol",
            "source",
        ]
    ]
