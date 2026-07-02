"""poe.ninja-style price source.

PoE1 public data lives under ``/api/data/{currencyoverview,itemoverview}``.  Path of Exile 2
economy on poe.ninja uses separate JSON under ``/poe2/api/economy/exchange/current/overview``,
with ``league`` set to the GGG league display name (e.g. ``Fate of the Vaal``).  When
``pricing_base_url`` ends with ``/api/data``, we try legacy PoE1 first for currency/fragments,
then fall back to the PoE2 exchange API on failure or empty ``lines`` (so old env files still
work for PoE2 leagues).  Without that suffix we call the PoE2 API directly.  Configure via
``settings.pricing_base_url``.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.logging import get_logger
from app.services.pricing.matcher import ItemKey
from app.services.pricing.source import PriceEstimate, PriceUnit

log = get_logger("app.services.pricing.poe_ninja")

# Bucket names on poe.ninja. Order matters for lookup precedence (uniques first).
UNIQUE_BUCKETS = [
    "UniqueArmour",
    "UniqueWeapon",
    "UniqueJewel",
    "UniqueAccessory",
    "UniqueFlask",
    "UniqueRelic",
    "UniqueMap",
]
CURRENCY_BUCKETS = ["Currency", "Fragment"]
POE2_ECONOMY_BUCKETS = [
    "LineageSupportGems",
    "UncutGems",
    "UniqueCharms",
    "UniqueFlasks",
]

# PoE2 ``type`` query value for the exchange overview (differs from bucket name for fragments).
POE2_OVERVIEW_TYPE = {"Currency": "Currency", "Fragment": "Fragments"}


def _uses_poe1_data_api(base_url: str) -> bool:
    return base_url.rstrip("/").endswith("/api/data")


def _poe2_site_origin(base_url: str) -> str:
    """HTTPS origin for PoE2 JSON (strip trailing ``/api/data`` if present)."""
    b = base_url.rstrip("/")
    if b.endswith("/api/data"):
        b = b[: -len("/api/data")].rstrip("/")
    parsed = urlparse(b if "://" in b else f"https://{b}")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "https://poe.ninja"


def normalize_poe2_exchange_overview(data: dict[str, Any]) -> dict[str, Any]:
    """Turn PoE2 ``/overview`` JSON into PoE1-style ``{"lines": [...]}`` with chaos equivalents.

    PoE2 prices are anchored in Divine; ``core.rates["chaos"]`` is chaos orbs per 1 divine.
    Each line's ``primaryValue`` is divine per one unit of that item/currency.
    """
    core = data.get("core") if isinstance(data.get("core"), dict) else {}
    rates = core.get("rates") if isinstance(core.get("rates"), dict) else {}
    chaos_per_divine = float(rates.get("chaos") or 0.0)
    if chaos_per_divine <= 0:
        for line in data.get("lines") or []:
            if not isinstance(line, dict):
                continue
            if str(line.get("id") or "") != "chaos":
                continue
            d_per_chaos = float(line.get("primaryValue") or 0.0)
            if d_per_chaos > 0:
                chaos_per_divine = 1.0 / d_per_chaos
            break
    if chaos_per_divine <= 0:
        return {"lines": []}

    id_to_name: dict[str, str] = {}
    for it in data.get("items") or []:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id") or "").strip()
        if not iid:
            continue
        name = str(it.get("name") or iid).strip()
        id_to_name[iid] = name or iid

    out_lines: list[dict[str, Any]] = []
    for line in data.get("lines") or []:
        if not isinstance(line, dict):
            continue
        lid = str(line.get("id") or "").strip()
        if not lid:
            continue
        name = id_to_name.get(lid, lid)
        d_per_unit = float(line.get("primaryValue") or 0.0)
        chaos_eq = d_per_unit * chaos_per_divine
        out_lines.append(
            {
                "currencyTypeName": name,
                "name": name,
                "chaosEquivalent": chaos_eq,
                "chaosValue": chaos_eq,
            }
        )
    return {"lines": out_lines}


class PoeNinjaSource:
    name = "poe.ninja"

    def __init__(self, base_url: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._poe1 = _uses_poe1_data_api(self._base)
        self._poe2_origin = _poe2_site_origin(self._base)
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_ts: dict[str, float] = {}
        self._ttl = 60 * 15
        self._poe2_league_resolve: dict[str, str] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def lookup(self, league: str, key: ItemKey) -> PriceEstimate | None:
        buckets: list[str]
        if key.category == "currency":
            buckets = CURRENCY_BUCKETS
        elif key.category == "lineage_gem":
            buckets = ["LineageSupportGems"]
        elif key.category == "skill_gem":
            buckets = ["UncutGems"]
        elif key.category == "unique_charm":
            buckets = ["UniqueCharms"]
        elif key.category == "unique_flask":
            buckets = ["UniqueFlasks"]
        elif key.category == "unique":
            buckets = UNIQUE_BUCKETS
        elif key.category == "gem_trade":
            return None
        else:
            return None

        for bucket in buckets:
            entry = await self._find(league, bucket, key)
            if entry is not None:
                return entry
        return None

    def _uncut_skill_gem_label(self, level: int) -> str:
        return f"uncut skill gem (level {level})"

    async def _find(self, league: str, bucket: str, key: ItemKey) -> PriceEstimate | None:
        data = await self._fetch_bucket(league, bucket)
        lines = data.get("lines", []) if isinstance(data, dict) else []
        if key.category == "skill_gem" and key.gem_level is not None:
            target_name = self._uncut_skill_gem_label(key.gem_level)
            for line in lines:
                name = str(line.get("currencyTypeName") or line.get("name") or "").lower()
                if name == target_name:
                    value = line.get("chaosValue") or line.get("chaosEquivalent")
                    if value is None:
                        continue
                    return PriceEstimate(
                        value=float(value),
                        unit=PriceUnit.CHAOS,
                        chaos_equiv=float(value),
                        source=self.name,
                        confidence=0.85,
                    )
            return None

        target_name = key.name.lower() if key.name else key.base_type.lower()
        for line in lines:
            name = str(line.get("currencyTypeName") or line.get("name") or "").lower()
            base = str(line.get("baseType") or "").lower()
            if name == target_name or base == key.base_type.lower():
                value = line.get("chaosValue") or line.get("chaosEquivalent")
                if value is None:
                    continue
                return PriceEstimate(
                    value=float(value),
                    unit=PriceUnit.CHAOS,
                    chaos_equiv=float(value),
                    source=self.name,
                    confidence=1.0,
                )
        return None

    async def _fetch_poe2_index_state(self) -> dict[str, Any]:
        url = f"{self._poe2_origin}/poe2/api/data/index-state"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else {}
        except httpx.HTTPError as exc:
            log.warning("pricing.poe2_index_state_failed", error=str(exc))
            return {}

    async def _resolve_poe2_league_name(self, league: str) -> str:
        key = league.strip()
        if key in self._poe2_league_resolve:
            return self._poe2_league_resolve[key]
        data = await self._fetch_poe2_index_state()
        wanted_l = key.lower()
        for ek in ("economyLeagues", "oldEconomyLeagues"):
            rows = data.get(ek) or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                url = str(row.get("url") or "").strip()
                if name.lower() == wanted_l or url.lower() == wanted_l:
                    self._poe2_league_resolve[key] = name
                    return name
        self._poe2_league_resolve[key] = key
        return key

    async def _fetch_poe2_overview(self, league: str, bucket: str) -> dict[str, Any]:
        type_param = POE2_OVERVIEW_TYPE.get(bucket, bucket)
        url = f"{self._poe2_origin}/poe2/api/economy/exchange/current/overview"
        league_eff = await self._resolve_poe2_league_name(league)
        params = {"league": league_eff, "type": type_param}
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            raw = resp.json()
        except httpx.HTTPError as exc:
            log.warning("pricing.fetch_failed", bucket=bucket, error=str(exc))
            return {}

        if not isinstance(raw, dict) or not raw.get("lines"):
            return {}
        return normalize_poe2_exchange_overview(raw)

    async def _fetch_bucket(self, league: str, bucket: str) -> dict[str, Any]:
        cache_key = f"{league}:{bucket}"
        now = time.monotonic()
        if cache_key in self._cache and now - self._cache_ts.get(cache_key, 0.0) < self._ttl:
            return self._cache[cache_key]

        if self._poe1 and get_settings().ggg_api_realm != "poe2":
            path = "currencyoverview" if bucket in CURRENCY_BUCKETS else "itemoverview"
            url = f"{self._base}/{path}"
            params = {"league": league, "type": bucket}
            data: dict[str, Any] = {}
            try:
                resp = await self._client.get(url, params=params)
                resp.raise_for_status()
                raw = resp.json()
                if isinstance(raw, dict):
                    data = raw
            except httpx.HTTPError as exc:
                log.warning("pricing.fetch_failed", bucket=bucket, error=str(exc))
                data = {}
            lines = data.get("lines") if isinstance(data.get("lines"), list) else []
            if not lines and bucket in (CURRENCY_BUCKETS + POE2_ECONOMY_BUCKETS):
                poe2 = await self._fetch_poe2_overview(league, bucket)
                if poe2.get("lines"):
                    if bucket in CURRENCY_BUCKETS:
                        log.info("pricing.poe2_fallback_after_poe1", bucket=bucket)
                    data = poe2
        else:
            data = await self._fetch_poe2_overview(league, bucket)

        self._cache[cache_key] = data
        self._cache_ts[cache_key] = now
        return data

    async def currency_chaos_map(self, league: str) -> dict[str, float]:
        """Lowercased currency display names -> chaos value (for trade listing conversion).

        Returns ``{}`` when the currency bucket could not be loaded so callers can merge
        config/static fallbacks instead of treating only ``chaos`` keys as a full map.
        """
        data = await self._fetch_bucket(league, "Currency")
        lines = data.get("lines", []) if isinstance(data, dict) else []
        if not isinstance(lines, list) or not lines:
            return {}
        out: dict[str, float] = {"chaos": 1.0, "chaos orb": 1.0}
        for line in lines:
            if not isinstance(line, dict):
                continue
            name = str(line.get("currencyTypeName") or line.get("name") or "").strip()
            v = line.get("chaosValue") or line.get("chaosEquivalent")
            if not name or v is None:
                continue
            out[name.lower()] = float(v)
        return out
