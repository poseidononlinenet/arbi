# EVE Online PLEX Arbitrage Market Bot

A lightweight CLI bot that scans public EVE Swagger Interface (ESI) market data and reports potential **PLEX arbitrage** routes between trade regions.

## What it does

- Pulls public buy/sell orders for PLEX (`type_id=44992`) from selected regions.
- Finds the best **buy location** (lowest sell order) and **sell location** (highest buy order).
- Computes net profit per unit after configurable:
  - broker fees
  - sales tax
  - hauling/risk cost
- Ranks and prints the top opportunities.

## Quick start

```bash
python3 plex_arbitrage_bot.py
```

## Common usage

Run once with default hubs (Jita, Amarr, Dodixie, Rens, Hek):

```bash
python3 plex_arbitrage_bot.py
```

Watch mode (refresh every 60 seconds):

```bash
python3 plex_arbitrage_bot.py --watch 60
```

Use custom regions:

```bash
python3 plex_arbitrage_bot.py --regions "10000002:Jita,10000043:Amarr,10000032:Dodixie"
```

Tune fee assumptions:

```bash
python3 plex_arbitrage_bot.py --broker-fee 0.02 --sales-tax 0.025 --hauling-cost 100000
```

## Notes

- This bot only reads public data from ESI; no auth required.
- It is an informational scanner, not an automated trader.
- Market conditions can change rapidly; always validate manually before trading.
