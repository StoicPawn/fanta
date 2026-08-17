from __future__ import annotations

import requests
import pandas as pd


class BigBallsSource:
    """Optional free-tier enrichment from Big Balls Sports Data.

    The useful endpoint for this project is the big-five xG leaderboard. It exposes
    xG/xA/npxG/xGChain/xGBuildup plus goals, assists, shots, key passes, matches and
    minutes, with history back to 2014. Rows are name-keyed, so reconciliation must
    remain fuzzy and confidence-tagged.
    """

    BASE = "https://api.bigballsdata.com/v1"
    LEAGUES = {
        "Serie A": "serie-a",
        "Premier League": "epl",
        "La Liga": "laliga",
        "Bundesliga": "bundesliga",
        "Ligue 1": "ligue-1",
    }

    def __init__(self, api_key: str, timeout: int = 30):
        if not api_key:
            raise ValueError("BigBalls API key required")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None):
        r = requests.get(
            self.BASE + path,
            params=params or {},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return payload.get("data", payload) if isinstance(payload, dict) else payload

    def xg_leaders(self, league: str, season: int | str, limit: int = 1000) -> pd.DataFrame:
        slug = self.LEAGUES.get(league, league)
        data = self._get(
            f"/leagues/{slug}/xg-leaders",
            {"season": season, "limit": limit, "min_minutes": 0},
        )
        rows = data.get("rows", data) if isinstance(data, dict) else data
        df = pd.DataFrame(rows or [])
        if df.empty:
            return df
        ren = {
            "player_name": "player",
            "xG": "xg",
            "xA": "xa",
            "npxG": "npxg",
            "xGChain": "xg_chain",
            "xGBuildup": "xg_buildup",
            "keyPasses": "key_passes",
        }
        df = df.rename(columns=ren)
        for c in ["xg", "xa", "npxg", "xg_chain", "xg_buildup", "goals", "assists", "shots", "key_passes", "matches", "minutes"]:
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["data_source_bigballs"] = f"bigballs:{slug}:{season}"
        return df

    def big_five_history(self, seasons: list[int | str], limit: int = 1000) -> pd.DataFrame:
        frames = []
        for league, slug in self.LEAGUES.items():
            for season in seasons:
                try:
                    x = self.xg_leaders(slug, season, limit=limit)
                    if len(x):
                        x["source_league"] = league
                        x["source_season"] = str(season)
                        frames.append(x)
                except Exception:
                    continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
