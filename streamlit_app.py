import pandas as pd
import streamlit as st
from cryptopulse.fetcher import fetch_prices, DEFAULT_COINS

st.set_page_config(page_title="CryptoPulse", layout="centered")

st.title("CryptoPulse")
st.caption("Live market snapshot, powered by CoinGecko")

coins = st.multiselect(
    "Coins to track",
    options=DEFAULT_COINS,
    default=DEFAULT_COINS,
)

if st.button("Refresh prices") or "prices" not in st.session_state:
    try:
        st.session_state["prices"] = fetch_prices(coins or DEFAULT_COINS)
    except Exception as exc:
        st.error(f"Fetch failed: {exc}")
        st.stop()

prices = st.session_state["prices"]

rows = []
for coin, data in sorted(prices.items()):
    rows.append({
        "Coin": coin,
        "Price (USD)": data["price"],
        "24h Change (%)": data["change_24h"],
    })

df = pd.DataFrame(rows)

st.dataframe(
    df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Price (USD)": st.column_config.NumberColumn(format="$%.2f"),
        "24h Change (%)": st.column_config.NumberColumn(format="%.2f%%"),
    },
)
