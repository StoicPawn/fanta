from __future__ import annotations
import os
import requests
import pandas as pd

BASE = "https://api.football-data.org/v4"

class FootballDataSource:
    """Authoritative roster backbone using football-data.org.

    Free registration is sufficient for the low request volume used here. Results are
    cached by the caller. The source is deliberately not treated as infallible: the
    coverage gate reconciles it against fantasy lists and optional official sources.
    """
    def __init__(self, token: str | None = None, timeout: int = 30):
        self.token = token or os.getenv("FOOTBALL_DATA_TOKEN")
        self.timeout = timeout

    def _get(self, path: str, params=None):
        if not self.token:
            raise RuntimeError("FOOTBALL_DATA_TOKEN mancante. Registrazione gratuita su football-data.org.")
        r = requests.get(BASE + path, params=params, headers={"X-Auth-Token": self.token}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def serie_a_teams(self, season_start_year: int) -> pd.DataFrame:
        data = self._get("/competitions/SA/teams", {"season": season_start_year})
        rows = []
        for t in data.get("teams", []):
            rows.append({"team_id": t["id"], "team": t["name"], "team_short": t.get("shortName"), "tla": t.get("tla")})
        return pd.DataFrame(rows)

    def serie_a_squads(self, season_start_year: int) -> pd.DataFrame:
        teams = self.serie_a_teams(season_start_year)
        rows = []
        for t in teams.to_dict("records"):
            data = self._get(f"/teams/{t['team_id']}")
            for p in data.get("squad", []):
                if p.get("position") == "Coach":
                    continue
                rows.append({
                    "source": "football-data.org",
                    "source_player_id": p.get("id"),
                    "player": p.get("name"),
                    "team": t["team"],
                    "team_tla": t.get("tla"),
                    "position_raw": p.get("position"),
                    "date_of_birth": p.get("dateOfBirth"),
                    "nationality": p.get("nationality"),
                })
        return pd.DataFrame(rows)
