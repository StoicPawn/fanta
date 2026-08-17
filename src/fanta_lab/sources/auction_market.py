from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from io import StringIO

import pandas as pd
import requests

DEFAULT_URL = "https://www.fantacalcio-online.com/it/asta-fantacalcio-stima-prezzi"


def _norm(text: object) -> str:
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", s)


@dataclass(frozen=True)
class MarketBucket:
    managers: int
    budget: int


def nearest_bucket(managers: int, budget: int) -> MarketBucket:
    return MarketBucket(8 if managers <= 8 else 10, 350 if budget < 425 else 500)


def load_real_auction_averages(url: str = DEFAULT_URL, timeout: int = 20) -> pd.DataFrame:
    """Load the public table of actual average auction prices.

    The upstream page may change its HTML. This adapter fails loudly if it cannot
    identify a player name and at least one auction-price column; callers should
    treat this source as an optional market prior, never as the player universe.
    """
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "fanta-auction-lab/1.0"})
    r.raise_for_status()
    tables = pd.read_html(StringIO(r.text))
    candidates: list[pd.DataFrame] = []
    for t in tables:
        t = t.copy()
        t.columns = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
        joined = " ".join(t.columns).lower()
        if "nome" in joined and ("350" in joined or "500" in joined):
            candidates.append(t)
    if not candidates:
        raise RuntimeError("Tabella prezzi d'asta reali non riconosciuta nella pagina pubblica")
    df = max(candidates, key=len)
    name_col = next(c for c in df.columns if "nome" in c.lower())
    role_col = next((c for c in df.columns if c.strip().lower() in {"rt", "ruolo"} or " ruolo" in c.lower()), None)
    team_col = next((c for c in df.columns if "squadra" in c.lower()), None)
    out = pd.DataFrame({"player_market": df[name_col].astype(str)})
    out["player_key"] = out.player_market.map(_norm)
    if role_col: out["role_market"] = df[role_col].astype(str)
    if team_col: out["team_market"] = df[team_col].astype(str)
    for managers in (8, 10):
        for budget in (350, 500):
            key = f"market_{managers}_{budget}"
            matches = [c for c in df.columns if str(managers) in c and str(budget) in c]
            if matches:
                out[key] = pd.to_numeric(df[matches[0]].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    market_cols = [c for c in out if c.startswith("market_")]
    if not market_cols:
        raise RuntimeError("Nessuna colonna prezzo d'asta riconosciuta")
    return out.drop_duplicates("player_key")


def attach_market_prior(players: pd.DataFrame, market: pd.DataFrame, managers: int, budget: int) -> pd.DataFrame:
    out = players.copy()
    out["player_key"] = out["player"].map(_norm)
    bucket = nearest_bucket(managers, budget)
    col = f"market_{bucket.managers}_{bucket.budget}"
    if col not in market:
        out["market_auction_price"] = pd.NA
        out["market_auction_source"] = "unavailable"
        return out.drop(columns="player_key")
    m = market[["player_key", col]].rename(columns={col: "_bucket_price"})
    out = out.merge(m, on="player_key", how="left")
    scale = budget / bucket.budget
    out["market_auction_price"] = pd.to_numeric(out.pop("_bucket_price"), errors="coerce") * scale
    out["market_auction_source"] = f"FCO actual averages {bucket.managers} teams/{bucket.budget} credits; scaled x{scale:.3f}"
    return out.drop(columns="player_key")
