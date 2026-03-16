#!/usr/bin/env python3
"""EVE Online PLEX arbitrage scanner using ESI public market data."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List

ESI_BASE = "https://esi.evetech.net/latest"
PLEX_TYPE_ID = 44992

# region_id: human-friendly name
DEFAULT_REGIONS = {
    10000002: "The Forge (Jita)",
    10000043: "Domain (Amarr)",
    10000032: "Sinq Laison (Dodixie)",
    10000030: "Heimatar (Rens)",
    10000042: "Metropolis (Hek)",
}


@dataclass
class RegionQuote:
    region_id: int
    region_name: str
    highest_buy: float
    lowest_sell: float


@dataclass
class Opportunity:
    buy_region: RegionQuote
    sell_region: RegionQuote
    gross_margin_per_unit: float
    net_margin_per_unit: float
    net_margin_percent: float


def fetch_json(url: str, timeout: float = 15.0):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "plex-arb-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_region_orders(region_id: int, type_id: int = PLEX_TYPE_ID) -> list[dict]:
    orders: list[dict] = []
    page = 1

    while True:
        query = urllib.parse.urlencode({"order_type": "all", "type_id": type_id, "page": page})
        url = f"{ESI_BASE}/markets/{region_id}/orders/?{query}"
        page_orders = fetch_json(url)
        if not page_orders:
            break
        orders.extend(page_orders)
        if len(page_orders) < 1000:
            break
        page += 1

    return orders


def summarize_region(region_id: int, region_name: str, type_id: int = PLEX_TYPE_ID) -> RegionQuote:
    orders = fetch_region_orders(region_id, type_id)
    buy_prices = [o["price"] for o in orders if o.get("is_buy_order")]
    sell_prices = [o["price"] for o in orders if not o.get("is_buy_order")]

    highest_buy = max(buy_prices) if buy_prices else 0.0
    lowest_sell = min(sell_prices) if sell_prices else 0.0
    return RegionQuote(region_id=region_id, region_name=region_name, highest_buy=highest_buy, lowest_sell=lowest_sell)


def calculate_opportunities(
    quotes: Iterable[RegionQuote],
    broker_fee_rate: float,
    sales_tax_rate: float,
    hauling_cost_per_unit: float,
) -> List[Opportunity]:
    quotes = list(quotes)
    opportunities: List[Opportunity] = []

    for buy_region in quotes:
        if buy_region.lowest_sell <= 0:
            continue
        for sell_region in quotes:
            if buy_region.region_id == sell_region.region_id or sell_region.highest_buy <= 0:
                continue

            purchase_cost = buy_region.lowest_sell * (1 + broker_fee_rate)
            proceeds = sell_region.highest_buy * (1 - broker_fee_rate - sales_tax_rate)
            net_margin = proceeds - purchase_cost - hauling_cost_per_unit
            gross_margin = sell_region.highest_buy - buy_region.lowest_sell

            if net_margin > 0:
                opportunities.append(
                    Opportunity(
                        buy_region=buy_region,
                        sell_region=sell_region,
                        gross_margin_per_unit=gross_margin,
                        net_margin_per_unit=net_margin,
                        net_margin_percent=(net_margin / purchase_cost) * 100,
                    )
                )

    opportunities.sort(key=lambda o: o.net_margin_per_unit, reverse=True)
    return opportunities


def print_snapshot(quotes: Iterable[RegionQuote], opportunities: Iterable[Opportunity], top_n: int) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n=== PLEX Arbitrage Snapshot @ {now} ===")
    print("\nRegional quotes (ISK per PLEX):")
    for quote in quotes:
        print(
            f"- {quote.region_name:<24} | best buy: {quote.highest_buy:>12,.2f} | best sell: {quote.lowest_sell:>12,.2f}"
        )

    print("\nTop opportunities:")
    ops = list(opportunities)[:top_n]
    if not ops:
        print("- No positive net arbitrage opportunities found under current fee assumptions.")
        return

    for i, op in enumerate(ops, start=1):
        print(
            f"{i:>2}. Buy in {op.buy_region.region_name} @ {op.buy_region.lowest_sell:,.2f} -> "
            f"sell in {op.sell_region.region_name} @ {op.sell_region.highest_buy:,.2f} | "
            f"gross {op.gross_margin_per_unit:,.2f} | net {op.net_margin_per_unit:,.2f} ISK ({op.net_margin_percent:.2f}%)"
        )


def parse_regions(regions_arg: str | None) -> dict[int, str]:
    if not regions_arg:
        return DEFAULT_REGIONS

    regions: dict[int, str] = {}
    for item in regions_arg.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            rid, name = item.split(":", 1)
            regions[int(rid)] = name.strip()
        else:
            rid = int(item)
            regions[rid] = f"Region {rid}"
    return regions


def run_once(args: argparse.Namespace) -> int:
    regions = parse_regions(args.regions)
    quotes: list[RegionQuote] = []

    for region_id, region_name in regions.items():
        try:
            quotes.append(summarize_region(region_id, region_name, args.type_id))
        except urllib.error.URLError as exc:
            print(f"[warn] Could not load region {region_id} ({region_name}): {exc}")

    if not quotes:
        print("No market data loaded. Check connectivity or region IDs.")
        return 1

    opportunities = calculate_opportunities(
        quotes,
        broker_fee_rate=args.broker_fee,
        sales_tax_rate=args.sales_tax,
        hauling_cost_per_unit=args.hauling_cost,
    )
    print_snapshot(quotes, opportunities, args.top)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan EVE market regions for PLEX arbitrage opportunities.")
    parser.add_argument("--type-id", type=int, default=PLEX_TYPE_ID, help="EVE item type ID (default: PLEX 44992)")
    parser.add_argument(
        "--regions",
        type=str,
        default=None,
        help="Comma-separated regions as '<id>:<name>' or '<id>'. Defaults to major trade hubs.",
    )
    parser.add_argument("--broker-fee", type=float, default=0.03, help="Broker fee rate for each transaction (default: 0.03)")
    parser.add_argument("--sales-tax", type=float, default=0.036, help="Sales tax rate when selling (default: 0.036)")
    parser.add_argument("--hauling-cost", type=float, default=0.0, help="Fixed hauling/risk cost per unit in ISK")
    parser.add_argument("--top", type=int, default=10, help="Number of top opportunities to print")
    parser.add_argument("--watch", type=int, default=0, help="Repeat every N seconds (0 = run once)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.watch <= 0:
        return run_once(args)

    while True:
        code = run_once(args)
        if code != 0:
            return code
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
