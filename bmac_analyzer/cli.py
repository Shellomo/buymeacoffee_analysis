import click
import json
from pathlib import Path
from datetime import datetime
import numpy as np
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from typing import Optional
from .analyzer import BuyMeACoffeeAnalyzer

console = Console()


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(np, 'integer') and isinstance(obj, np.integer):
            return int(obj)
        if hasattr(np, 'floating') and isinstance(obj, np.floating):
            return float(obj)
        if hasattr(np, 'ndarray') and isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


def format_currency(amount: float) -> str:
    """Format amount as currency"""
    return f"${amount:,.2f}"


def get_cache_dir() -> Path:
    """Get the cache directory path and create it if it doesn't exist."""
    cache_dir = Path.home() / ".bmac-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Buy Me a Coffee Creator Stats Analyzer CLI"""
    pass


@cli.command()
@click.argument("creator_id")
@click.option("--no-cache", is_flag=True, help="Bypass cache and fetch fresh data")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table",
              help="Output format (table or json)")
@click.option("--coffee-price", "-p", type=float, default=5.0,
              help="Price per coffee in USD (default: $5.00)")
def stats(creator_id: str, no_cache: bool, format: str, coffee_price: float):
    """Get statistics for a Buy Me a Coffee creator"""
    try:
        with console.status(f"[bold green]Analyzing stats for {creator_id}..."):
            analyzer = BuyMeACoffeeAnalyzer(creator_id, use_cache=not no_cache)
            stats = analyzer.analyze_stats(coffee_price=coffee_price)

        if format == "json":
            click.echo(json.dumps(stats, indent=2, cls=NumpyEncoder))
        else:
            _display_stats_tables(stats, creator_id, coffee_price)

    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument("creator_id")
@click.option("--clear", is_flag=True, help="Clear cache for the specified creator")
def cache(creator_id: str, clear: bool):
    """Manage cache for a creator"""
    cache_dir = get_cache_dir()
    cache_file = cache_dir / f"{creator_id}.json"

    if clear:
        if cache_file.exists():
            cache_file.unlink()
            console.print(f"[green]Cache cleared for {creator_id}")
        else:
            console.print(f"[yellow]No cache exists for {creator_id}")
    else:
        if cache_file.exists():
            stats = {
                "size": f"{cache_file.stat().st_size / 1024:.2f} KB",
                "last_modified": datetime.fromtimestamp(cache_file.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }
            _display_cache_info(creator_id, stats)
        else:
            console.print(f"[yellow]No cache exists for {creator_id}")


@cli.command()
def clear_all():
    """Clear all cached data"""
    cache_dir = get_cache_dir()

    if not any(cache_dir.iterdir()):
        console.print("[yellow]Cache is already empty")
        return

    with console.status("[bold red]Clearing all cached data..."):
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()

    console.print("[green]All cache cleared successfully")


def _display_stats_tables(stats: dict, creator_id: str, coffee_price: float):
    """Display statistics in formatted tables"""
    if "Failed" in stats:
        console.print(f"[bold red]{stats['Failed']}")
        return

    # Summary Table
    summary_table = Table(title=f"📊 Statistics for {creator_id}", show_header=True)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green", justify="right")

    summary = stats["summary"]
    summary_table.add_row("Total Supporters", str(summary["total_supporters"]))
    summary_table.add_row("Total Coffees", str(summary["total_coffees"]))
    summary_table.add_row("Total Earnings", format_currency(summary["total_earnings"]))
    summary_table.add_row("Avg Coffees/Supporter", f"{summary['average_coffees_per_supporter']:.2f}")
    summary_table.add_row("Avg Earnings/Supporter", format_currency(summary["average_earnings_per_supporter"]))
    summary_table.add_row("First Support", summary["first_support"])
    summary_table.add_row("Last Support", summary["last_support"])
    summary_table.add_row("Days Active", str(summary["days_active"]))

    console.print(summary_table)
    console.print()

    # Support Patterns Table
    patterns_table = Table(title="👥 Support Patterns", show_header=True)
    patterns_table.add_column("Type", style="cyan")
    patterns_table.add_column("Count", style="green", justify="right")

    patterns = stats["support_patterns"]
    for coffees, count in sorted(patterns["coffee_distribution"].items(), key=lambda x: int(x[0])):
        total_amount = int(coffees) * coffee_price * count
        patterns_table.add_row(
            f"{coffees} Coffee{'s' if int(coffees) > 1 else ''}",
            f"{count} ({format_currency(total_amount)})"
        )

    patterns_table.add_row("With Messages", str(patterns["supporters_with_messages"]))
    patterns_table.add_row("Message Rate", patterns["message_rate"])
    patterns_table.add_row("Creator Supporters", str(patterns["creator_supporters"]))

    console.print(patterns_table)
    console.print()

    # Monthly Trends Table
    trends_table = Table(title="📈 Monthly Trends", show_header=True)
    trends_table.add_column("Period", style="cyan")
    trends_table.add_column("Coffees", style="green", justify="right")
    trends_table.add_column("Earnings", style="green", justify="right")

    trends = stats["monthly_trends"]

    # Best Month
    trends_table.add_row(
        f"Best Month ({trends['best_month']['date']})",
        str(trends['best_month']['coffees']),
        format_currency(trends['best_month']['earnings'])
    )

    # Worst Month
    trends_table.add_row(
        f"Worst Month ({trends['worst_month']['date']})",
        str(trends['worst_month']['coffees']),
        format_currency(trends['worst_month']['earnings'])
    )

    # Monthly Averages
    trends_table.add_row(
        "Monthly Average",
        f"{trends['monthly_averages']['coffees']:.1f}",
        format_currency(trends['monthly_averages']['earnings'])
    )

    console.print(trends_table)


def _display_cache_info(creator_id: str, stats: dict):
    """Display cache information in a formatted table"""
    table = Table(title=f"💾 Cache Info for {creator_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


if __name__ == "__main__":
    cli()