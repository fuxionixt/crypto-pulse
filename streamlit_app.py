import datetime
import os
import pandas as pd
import streamlit as st
import plotly.express as px
from cryptopulse.fetcher import fetch_prices, fetch_gas_price, DEFAULT_COINS
from cryptopulse.agent import ask_agent

st.set_page_config(page_title="CryptoPulse", layout="centered")

st.title("CryptoPulse")
st.caption("Live market snapshot, powered by CoinGecko")

CURRENCY_SYMBOLS = {"usd": "$", "eur": "€", "gbp": "£"}


def get_secret(key: str) -> str | None:
    """Read a secret from Streamlit's secrets.toml if available, else from env vars (Railway)."""
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key)


# --- Sidebar controls ---
with st.sidebar:
    st.header("Settings")
    coins = st.multiselect(
        "Coins to track",
        options=DEFAULT_COINS,
        default=DEFAULT_COINS,
    )
    currency = st.selectbox(
        "Currency",
        options=["usd", "eur", "gbp"],
        format_func=lambda c: c.upper(),
        index=0,
    )
    refresh_clicked = st.button("Refresh prices", use_container_width=True)

symbol = CURRENCY_SYMBOLS.get(currency, "$")

currency_changed = st.session_state.get("currency") != currency
if refresh_clicked or "prices" not in st.session_state or currency_changed:
    try:
        st.session_state["prices"] = fetch_prices(coins or DEFAULT_COINS, currency=currency)
        st.session_state["last_updated"] = datetime.datetime.now()
        st.session_state["currency"] = currency
    except Exception as exc:
        st.error(f"Fetch failed: {exc}")
        st.stop()

prices = st.session_state["prices"]

rows = []
for coin, data in sorted(prices.items()):
    rows.append({
        "Coin": coin,
        "Price": data["price"],
        "24h Change (%)": data["change_24h"],
    })

df = pd.DataFrame(rows)


def format_price(p: float) -> str:
    if p >= 1000:
        return f"{symbol}{p/1000:.1f}k"
    if p >= 1:
        return f"{symbol}{p:.2f}"
    return f"{symbol}{p:.4f}"


# --- Fetch gas price early so it can appear in the top summary bar ---
gas_data = None
gas_error = None
try:
    eia_key = get_secret("EIA_API_KEY")
    if not eia_key:
        raise ValueError("EIA_API_KEY not found in secrets or environment variables")
    gas_data = fetch_gas_price(eia_key)
except Exception as exc:
    gas_error = str(exc)

# --- Top summary bar: all prices at a glance ---
st.markdown("#### Quick glance")
summary_cols = st.columns(len(rows) + 1)
for col, row in zip(summary_cols, rows):
    col.metric(row["Coin"], format_price(row["Price"]), f"{row['24h Change (%)']:.2f}%")

with summary_cols[-1]:
    if gas_data:
        st.metric("⛽ US Gas/gal", f"${gas_data['price_per_gallon']:.3f}")
    else:
        st.metric("⛽ US Gas/gal", "N/A")

st.divider()

last_updated = st.session_state.get("last_updated")
if last_updated:
    st.caption(f"Last updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')} ({currency.upper()})")

# --- Top gainer / loser callout ---
if len(df) > 1:
    top_gainer = df.loc[df["24h Change (%)"].idxmax()]
    top_loser = df.loc[df["24h Change (%)"].idxmin()]
    c1, c2 = st.columns(2)
    c1.success(f"📈 Top gainer: **{top_gainer['Coin']}** ({top_gainer['24h Change (%)']:.2f}%)")
    c2.error(f"📉 Top loser: **{top_loser['Coin']}** ({top_loser['24h Change (%)']:.2f}%)")

# --- Full data table ---
st.dataframe(
    df.drop(columns=["Direction"], errors="ignore"),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Price": st.column_config.NumberColumn(format=f"{symbol}%.2f"),
        "24h Change (%)": st.column_config.NumberColumn(format="%.2f%%"),
    },
)

# --- US Gas Price detail ---
st.divider()
st.subheader("⛽ US Gas Price")
if gas_data:
    st.metric(
        "Regular Gasoline (US avg, per gallon)",
        f"${gas_data['price_per_gallon']:.3f}",
    )
    st.caption(f"Week of {gas_data['period']} · Source: EIA Gasoline and Diesel Fuel Update")
else:
    st.warning(f"Couldn't load gas price: {gas_error}")

# --- Graph: price comparison across coins ---
st.subheader(f"Price comparison ({currency.upper()})")
fig_price = px.bar(
    df, x="Coin", y="Price", log_y=True,
    title=None, text_auto=".2s",
)
fig_price.update_layout(margin=dict(t=10, b=10))
st.plotly_chart(fig_price, use_container_width=True)

# --- Graph: 24h change across coins ---
st.subheader("24h change")
df["Direction"] = df["24h Change (%)"].apply(lambda x: "Up" if x >= 0 else "Down")
fig_change = px.bar(
    df, x="Coin", y="24h Change (%)", color="Direction",
    color_discrete_map={"Up": "#2ecc71", "Down": "#e74c3c"},
    title=None,
)
fig_change.update_layout(margin=dict(t=10, b=10), showlegend=False)
st.plotly_chart(fig_change, use_container_width=True)

# --- Prediction game ---
st.divider()
st.subheader("🎲 Predict the next move")

if "score" not in st.session_state:
    st.session_state["score"] = 0
if "pending_prediction" not in st.session_state:
    st.session_state["pending_prediction"] = None

pred_col1, pred_col2, pred_col3 = st.columns([2, 1, 1])
with pred_col1:
    predict_coin = st.selectbox("Pick a coin", options=[r["Coin"] for r in rows], key="predict_coin")
with pred_col2:
    if st.button("📈 Predict UP", use_container_width=True):
        current_price = next(r["Price"] for r in rows if r["Coin"] == predict_coin)
        st.session_state["pending_prediction"] = {
            "coin": predict_coin, "direction": "up", "price_at_bet": current_price,
        }
with pred_col3:
    if st.button("📉 Predict DOWN", use_container_width=True):
        current_price = next(r["Price"] for r in rows if r["Coin"] == predict_coin)
        st.session_state["pending_prediction"] = {
            "coin": predict_coin, "direction": "down", "price_at_bet": current_price,
        }

pending = st.session_state["pending_prediction"]
if pending:
    st.info(
        f"Prediction locked: **{pending['coin']}** will go **{pending['direction'].upper()}** "
        f"from {symbol}{pending['price_at_bet']:.4f}. Click Refresh prices to check the result."
    )

# --- Ask CryptoPulse (agent) ---
st.divider()
st.subheader("💬 Ask CryptoPulse")

with st.expander("Your holdings (optional, for portfolio questions)"):
    holdings_input = st.text_area(
        "Enter as coin: amount, one per line",
        placeholder="bitcoin: 0.5\nethereum: 3",
    )

user_query = st.text_input("Ask something, e.g. \"what's my portfolio worth if BTC hits 100k?\"")

if st.button("Ask") and user_query:
    holdings = {}
    for line in holdings_input.splitlines():
        if ":" in line:
            coin, amount = line.split(":", 1)
            try:
                holdings[coin.strip()] = float(amount.strip())
            except ValueError:
                pass

    with st.spinner("Thinking..."):
        try:
            answer = ask_agent(user_query, holdings=holdings or None)
            st.write(answer)
        except Exception as exc:
            st.error(f"Agent failed: {exc}")

# Resolve prediction on refresh
if refresh_clicked and pending:
    new_price = next((r["Price"] for r in rows if r["Coin"] == pending["coin"]), None)
    if new_price is not None:
        went_up = new_price > pending["price_at_bet"]
        correct = (went_up and pending["direction"] == "up") or (not went_up and pending["direction"] == "down")
        if correct:
            st.session_state["score"] += 10
            st.success(f"✅ Correct! {pending['coin']} moved as predicted. +10 points")
        else:
            st.session_state["score"] -= 5
            st.error(f"❌ Wrong! {pending['coin']} moved the other way. -5 points")
    st.session_state["pending_prediction"] = None

st.metric("Your score", st.session_state["score"])