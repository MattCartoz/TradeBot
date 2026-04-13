"""External data sources — fetches real market data from free APIs.

These are the actual data pipelines that feed the analyst agents
with real information rather than asking them to hallucinate.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# Shared async client — reused across all fetchers
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


# ─── Fear & Greed Index (Alternative.me) ──────────────────────────
# FREE, no API key required.

async def fetch_fear_greed() -> dict:
    """Fetch the Crypto Fear & Greed Index.

    Returns:
        {
            "value": 72,
            "label": "Greed",
            "timestamp": "2026-04-13",
            "history_7d": [{"value": 68, "label": "Greed"}, ...]
        }
    """
    client = await _get_client()
    try:
        resp = await client.get("https://api.alternative.me/fng/?limit=7&format=json")
        resp.raise_for_status()
        data = resp.json()["data"]
        current = data[0]
        return {
            "value": int(current["value"]),
            "label": current["value_classification"],
            "timestamp": datetime.fromtimestamp(
                int(current["timestamp"]), tz=timezone.utc
            ).strftime("%Y-%m-%d"),
            "history_7d": [
                {"value": int(d["value"]), "label": d["value_classification"]}
                for d in data
            ],
        }
    except Exception as e:
        logger.error("Fear & Greed fetch failed: %s", e)
        return {"value": 50, "label": "Neutral", "timestamp": "N/A", "history_7d": []}


# ─── FRED Economic Data (Federal Reserve) ────────────────────────
# FREE, requires API key from https://fred.stlouisfed.org/docs/api/api_key.html
# But we'll use the public observation endpoint for key indicators.

FRED_SERIES = {
    "DFF": "Federal Funds Rate",
    "T10Y2Y": "10Y-2Y Treasury Spread (recession indicator)",
    "CPIAUCSL": "CPI (inflation)",
    "UNRATE": "Unemployment Rate",
    "VIXCLS": "VIX (volatility index)",
}


async def fetch_fred_data(api_key: str | None = None) -> dict:
    """Fetch key economic indicators from FRED.

    Returns dict of indicator name → latest value + direction.
    Works without API key using the public series endpoint.
    """
    client = await _get_client()
    results = {}

    for series_id, name in FRED_SERIES.items():
        try:
            url = f"https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "sort_order": "desc",
                "limit": "2",
                "file_type": "json",
            }
            if api_key:
                params["api_key"] = api_key
            else:
                # Without API key, try the public access
                params["api_key"] = "DEMO_KEY"

            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                observations = resp.json().get("observations", [])
                if observations:
                    current = observations[0]
                    previous = observations[1] if len(observations) > 1 else None
                    current_val = current.get("value", ".")
                    if current_val != ".":
                        val = float(current_val)
                        direction = "unchanged"
                        if previous and previous.get("value", ".") != ".":
                            prev_val = float(previous["value"])
                            direction = "rising" if val > prev_val else "falling" if val < prev_val else "unchanged"
                        results[name] = {
                            "value": val,
                            "date": current.get("date", ""),
                            "direction": direction,
                        }
        except Exception as e:
            logger.warning("FRED fetch failed for %s: %s", series_id, e)

    return results


# ─── DeFiLlama (On-Chain / DeFi Data) ────────────────────────────
# FREE, no API key, no auth.

async def fetch_defi_tvl() -> dict:
    """Fetch total DeFi TVL and top protocols from DeFiLlama.

    Returns:
        {
            "total_tvl": 150_000_000_000,
            "total_tvl_formatted": "$150.0B",
            "top_protocols": [{"name": "Lido", "tvl": 30B, ...}, ...],
            "chains": {"ethereum": 60B, "solana": 12B, ...}
        }
    """
    client = await _get_client()
    result = {"total_tvl": 0, "total_tvl_formatted": "N/A", "top_protocols": [], "chains": {}}

    try:
        # Total TVL
        resp = await client.get("https://api.llama.fi/v2/historicalChainTvl")
        if resp.status_code == 200:
            data = resp.json()
            if data:
                latest = data[-1]
                tvl = latest.get("tvl", 0)
                result["total_tvl"] = tvl
                result["total_tvl_formatted"] = f"${tvl / 1e9:.1f}B"
    except Exception as e:
        logger.warning("DeFiLlama TVL fetch failed: %s", e)

    try:
        # Top protocols
        resp = await client.get("https://api.llama.fi/protocols")
        if resp.status_code == 200:
            protocols = resp.json()
            top = sorted(protocols, key=lambda p: p.get("tvl", 0), reverse=True)[:10]
            result["top_protocols"] = [
                {
                    "name": p["name"],
                    "tvl": p.get("tvl", 0),
                    "tvl_formatted": f"${p.get('tvl', 0) / 1e9:.2f}B",
                    "change_1d": p.get("change_1d", 0),
                    "category": p.get("category", ""),
                    "chains": p.get("chains", []),
                }
                for p in top
            ]
    except Exception as e:
        logger.warning("DeFiLlama protocols fetch failed: %s", e)

    try:
        # Chain TVL breakdown
        resp = await client.get("https://api.llama.fi/v2/chains")
        if resp.status_code == 200:
            chains = resp.json()
            top_chains = sorted(chains, key=lambda c: c.get("tvl", 0), reverse=True)[:10]
            result["chains"] = {
                c["name"]: {
                    "tvl": c.get("tvl", 0),
                    "tvl_formatted": f"${c.get('tvl', 0) / 1e9:.1f}B",
                }
                for c in top_chains
            }
    except Exception as e:
        logger.warning("DeFiLlama chains fetch failed: %s", e)

    return result


# ─── Aggregator — fetch all external data at once ────────────────

async def fetch_all_external_data(fred_api_key: str | None = None) -> dict:
    """Fetch all external data sources in parallel.

    Returns a dict with all data organized by type:
    {
        "fear_greed": {...},
        "macro": {...},
        "defi": {...},
        "fetched_at": "2026-04-13T12:00:00"
    }
    """
    import asyncio

    fear_greed_task = fetch_fear_greed()
    fred_task = fetch_fred_data(fred_api_key)
    defi_task = fetch_defi_tvl()

    fear_greed, fred, defi = await asyncio.gather(
        fear_greed_task, fred_task, defi_task,
        return_exceptions=True,
    )

    return {
        "fear_greed": fear_greed if not isinstance(fear_greed, Exception) else {},
        "macro": fred if not isinstance(fred, Exception) else {},
        "defi": defi if not isinstance(defi, Exception) else {},
        "fetched_at": datetime.utcnow().isoformat(),
    }


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
