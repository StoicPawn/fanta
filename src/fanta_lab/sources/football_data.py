from __future__ import annotations

import time
import requests
import pandas as pd

from ..config import get_secret

BASE = "https://api.football-data.org/v4"


class FootballDataSource:
    """Roster backbone using football-data.org with rate-limit awareness.

    The token is resolved at runtime only. It is never written to disk by this class.
    Response rate-limit headers are retained so the UI can surface remaining quota.
    """

    def __init__(self, token: str | None = None, timeout: int = 30, min_interval: float = 0.35):
        self.token = get_secret("FOOTBALL_DATA_TOKEN", token)
        self.timeout = timeout
        self.min_interval = float(max(0, min_interval))
        self._last_request = 0.0
        self.last_rate_limit: dict[str, str | int | None] = {}

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    @staticmethod
    def _rate_headers(headers) -> dict:
        interesting = {}
        for k, v in headers.items():
            lk = str(k).lower()
            if "requestcounter" in lk or "ratelimit" in lk or "retry-after" in lk:
                try:
                    interesting[k] = int(v)
                except Exception:
                    interesting[k] = v
        return interesting

    def _get(self, path: str, params=None):
        if not self.token:
            raise RuntimeError(
                "FOOTBALL_DATA_TOKEN mancante. Configuralo come variabile d'ambiente, "
                "Streamlit secret o inseriscilo nella sessione dell'interfaccia."
            )
        self._throttle()
        r = requests.get(
            BASE + path,
            params=params,
            headers={"X-Auth-Token": self.token, "User-Agent": "fanta-auction-lab/1.0"},
            timeout=self.timeout,
        )
        self._last_request = time.monotonic()
        self.last_rate_limit = self._rate_headers(r.headers)
        if r.status_code == 429:
            retry = r.headers.get("Retry-After", "unknown")
            raise RuntimeError(f"football-data.org rate limit raggiunto; Retry-After={retry}")
        if r.status_code in (401, 403):
            raise RuntimeError("football-data.org ha rifiutato il token: verifica che sia attivo e corretto.")
        r.raise_for_status()
        return r.json()

    def ping(self) -> dict:
        data = self._get("/competitions/SA")
        return {
            "ok": bool(data.get("id")),
            "competition": data.get("name"),
            "code": data.get("code"),
            "rate_limit": self.last_rate_limit.copy(),
        }

    def serie_a_teams(self, season_start_year: int) -> pd.DataFrame:
        data = self._get("/competitions/SA/teams", {"season": season_start_year})
        rows = []
        for t in data.get("teams", []):
            rows.append({
                "team_id": t["id"],
                "team": t["name"],
                "team_short": t.get("shortName"),
                "tla": t.get("tla"),
            })
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
