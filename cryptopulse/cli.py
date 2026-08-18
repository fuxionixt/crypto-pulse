
"""Command-line entry point for CryptoPulse."""

from rich.console import Console
from rich.table import Table

from cryptopulse.fetcher import fetch_prices


def main() -> None:
    console = Console()
    console.print("[bold cyan]CryptoPulse[/] — live market snapshot\n")

    try:
        prices = fetch_prices()
    except Exception as exc:
        console.print(f"[red]Fetch failed:[/] {exc}")
        return

    table = Table(title="Live Prices (USD)")
    table.add_column("Coin", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("24h %", justify="right")

    for coin, data in sorted(prices.items()):
        change = data["change_24h"]
        color = "green" if change >= 0 else "red"
        table.add_row(coin, f"${data['price']:,.2f}", f"[{color}]{change:+.2f}%[/]")

    console.print(table)


if __name__ == "__main__":
    main()