import json
import os
import streamlit as st
from anthropic import Anthropic
from cryptopulse.fetcher import fetch_prices, DEFAULT_COINS


def _get_anthropic_key() -> str | None:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY")


client = Anthropic(api_key=_get_anthropic_key())

TOOLS = [
    {
        "name": "get_price",
        "description": "Get the current price and 24h change for one or more cryptocurrencies, in a given currency.",
        "input_schema": {
            "type": "object",
            "properties": {
                "coins": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Coin IDs, e.g. ['bitcoin', 'ethereum']",
                },
                "currency": {
                    "type": "string",
                    "description": "Currency code, e.g. 'usd', 'eur', 'gbp'",
                    "default": "usd",
                },
            },
            "required": ["coins"],
        },
    },
    {
        "name": "get_portfolio_value",
        "description": "Given a dict of coin holdings (amount owned per coin) and optional hypothetical prices, calculate total portfolio value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "holdings": {
                    "type": "object",
                    "description": "Map of coin id -> amount held, e.g. {'bitcoin': 0.5}",
                },
                "hypothetical_prices": {
                    "type": "object",
                    "description": "Optional override prices per coin, e.g. {'bitcoin': 100000} for 'what if BTC hits 100k'",
                },
                "currency": {"type": "string", "default": "usd"},
            },
            "required": ["holdings"],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> str:
    """Run the real function behind a tool call and return a string result."""
    if name == "get_price":
        coins = tool_input.get("coins", DEFAULT_COINS)
        currency = tool_input.get("currency", "usd")
        prices = fetch_prices(coins, currency=currency)
        return json.dumps(prices)

    if name == "get_portfolio_value":
        holdings = tool_input.get("holdings", {})
        overrides = tool_input.get("hypothetical_prices", {})
        currency = tool_input.get("currency", "usd")

        coins_needed = list(holdings.keys())
        live_prices = fetch_prices(coins_needed, currency=currency)

        total = 0.0
        breakdown = {}
        for coin, amount in holdings.items():
            price = overrides.get(coin, live_prices.get(coin, {}).get("price", 0))
            value = amount * price
            breakdown[coin] = {"amount": amount, "price_used": price, "value": value}
            total += value

        return json.dumps({"total_value": total, "currency": currency, "breakdown": breakdown})

    return json.dumps({"error": f"Unknown tool: {name}"})


def ask_agent(user_query: str, holdings: dict | None = None) -> str:
    """Send a natural-language query to Claude, letting it call tools as needed."""
    system = (
        "You are CryptoPulse's assistant. Use the get_price and get_portfolio_value "
        "tools to answer questions about crypto prices and portfolio value. "
        "For hypothetical questions like 'what if BTC hits 100k', pass that price "
        "in hypothetical_prices rather than fetching the live price for that coin."
    )
    if holdings:
        system += f" The user's current holdings are: {json.dumps(holdings)}."

    messages = [{"role": "user", "content": user_query}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks)

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})