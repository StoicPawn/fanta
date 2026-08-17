from __future__ import annotations

import io
import requests
import pandas as pd


class FootballDataUKSource:
    """Free historical Serie A/Serie B match CSVs from football-data.co.uk.

    Used for team environment only: goals for/against, shots, shots on target,
    corners and cards. This is intentionally not a player-stat source.
    """

    BASE = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    @staticmethod
    def season_code(start_year: int) -> str:
        return f"{str(start_year)[2:]}{str(start_year + 1)[2:]}"

    def matches(self, start_year: int, division: str = "I1") -> pd.DataFrame:
        url = self.BASE.format(season=self.season_code(start_year), division=division)
        r = requests.get(url, timeout=self.timeout, headers={"User-Agent": "fanta-auction-lab/1.0"})
        r.raise_for_status()
        return pd.read_csv(io.BytesIO(r.content))

    def team_features(self, start_year: int, division: str = "I1") -> pd.DataFrame:
        df = self.matches(start_year, division)
        wanted = ["HomeTeam", "AwayTeam", "FTHG", "FTAG", "HS", "AS", "HST", "AST", "HC", "AC", "HY", "AY", "HR", "AR"]
        for c in wanted:
            if c not in df:
                df[c] = 0
            if c not in {"HomeTeam", "AwayTeam"}:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        rows = []
        for _, r in df.iterrows():
            rows.append({"team": r.HomeTeam, "gf": r.FTHG, "ga": r.FTAG, "shots": r.HS, "shots_against": r.AS, "sot": r.HST, "sot_against": r.AST, "corners": r.HC, "yellow": r.HY, "red": r.HR})
            rows.append({"team": r.AwayTeam, "gf": r.FTAG, "ga": r.FTHG, "shots": r.AS, "shots_against": r.HS, "sot": r.AST, "sot_against": r.HST, "corners": r.AC, "yellow": r.AY, "red": r.AR})
        x = pd.DataFrame(rows)
        if x.empty:
            return x
        agg = x.groupby("team", as_index=False).agg(
            matches=("gf", "size"), goals_for=("gf", "sum"), goals_against=("ga", "sum"),
            shots_for=("shots", "sum"), shots_against=("shots_against", "sum"),
            sot_for=("sot", "sum"), sot_against=("sot_against", "sum"), corners=("corners", "sum"),
            yellow=("yellow", "sum"), red=("red", "sum"),
        )
        for c in ["goals_for", "goals_against", "shots_for", "shots_against", "sot_for", "sot_against", "corners", "yellow", "red"]:
            agg[c + "_pg"] = agg[c] / agg["matches"].clip(lower=1)
        # Priors centered at 1; >1 means stronger attack / weaker defence respectively.
        lg_gf = max(0.1, agg.goals_for_pg.mean())
        lg_ga = max(0.1, agg.goals_against_pg.mean())
        agg["team_attack_strength"] = (agg.goals_for_pg / lg_gf).clip(.55, 1.65)
        agg["team_defense_concede_factor"] = (agg.goals_against_pg / lg_ga).clip(.55, 1.65)
        agg["team_defense_strength"] = (1 / agg.team_defense_concede_factor).clip(.55, 1.65)
        agg["team_context_source"] = f"football-data.co.uk:{start_year}-{start_year+1}:{division}"
        return agg
