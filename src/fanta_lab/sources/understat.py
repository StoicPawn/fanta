from __future__ import annotations
import json, re
import requests
import pandas as pd

class UnderstatSource:
    """Public-data adapter for Understat league player aggregates.

    Provides historical/current xG-style metrics for independent projections. It is
    an enrichment source, never the roster authority.
    """
    URL = "https://understat.com/league/Serie_A/{season}"
    def __init__(self, timeout: int = 30): self.timeout = timeout

    def league_players(self, season_start_year: int) -> pd.DataFrame:
        r = requests.get(self.URL.format(season=season_start_year), timeout=self.timeout,
                         headers={"User-Agent": "Mozilla/5.0 FantaAuctionLab/0.2"})
        r.raise_for_status()
        m = re.search(r"playersData\s*=\s*JSON\.parse\('(.+?)'\)", r.text, flags=re.S)
        if not m:
            raise RuntimeError("Understat playersData non trovato; usare CSV di enrichment o aggiornare adapter.")
        raw = bytes(m.group(1), "utf-8").decode("unicode_escape")
        data = json.loads(raw)
        df = pd.DataFrame(data)
        ren = {"player_name":"player", "team_title":"team_understat", "time":"minutes", "xG":"xg", "xA":"xa", "npxG":"npxg", "xGChain":"xg_chain", "xGBuildup":"xg_buildup"}
        df = df.rename(columns=ren)
        numeric = ["games","minutes","goals","assists","shots","key_passes","xg","xa","npxg","xg_chain","xg_buildup","yellow_cards","red_cards"]
        for c in numeric:
            if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
        df["source_stats"] = "understat-public"
        return df
