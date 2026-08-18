"""Fetch live market data from the CoinGecko public API."""

import requests

API_URL = "https://api.coingecko.com/api/v3/simple/price"
DEFAULT_COINS = ["bitcoin", "ethereum", "solana", "ripple", "cardano", "avalanche-2"]
EIA_SERIES_ID = "PET.EMM_EPMR_PTE_NUS_DPG.W"  # US weekly regular gasoline, $/gallon

def fetch_gas_price(api_key: str) -> dict:
    """Return the latest US national average regular gasoline price per gallon.

    Source: EIA Gasoline and Diesel Fuel Update (published weekly, Mondays).
    Raises requests.RequestException if the network call fails.
    """
    url = f"https://api.eia.gov/v2/seriesid/{EIA_SERIES_ID}"
    response = requests.get(url, params={"api_key": api_key}, timeout=10)
    response.raise_for_status()
    data = response.json()

    series = data["response"]["data"]
    latest = series[0]  # most recent entry first
    return {
        "price_per_gallon": float(latest["value"]),
        "period": latest["period"],  # date string, e.g. "2026-08-11"
    }
def fetch_prices(coins: list[str] | None = None, currency: str = "usd") -> dict:
    """Return {coin: {"price": float, "change_24h": float}} for each coin.

    Raises requests.RequestException if the network call fails.
    """
    coins = coins or DEFAULT_COINS
    params = {
        "ids": ",".join(coins),
        "vs_currencies": currency,
        "include_24hr_change": "true",
    }
    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status()
    raw = response.json()

    result = {}
    for coin, values in raw.items():
        result[coin] = {
            "price": float(values[currency]),
            "change_24h": float(values.get(f"{currency}_24h_change") or 0.0),
        }
    return result