from __future__ import annotations

import codecs
import html
import io
import json
import re

import pandas as pd
import requests


class UnderstatSource:
    """Public-data adapter for Understat league player aggregates.

    Primary path: parse the public Understat league page.
    Historical fallback: a public GitHub mirror of aggregated Understat player data.
    The fallback is important in CI environments where understat.com may block or
    vary HTML responses.  Both paths expose the same normalized fields.
    """

    URL = "https://understat.com/league/Serie_A/{season}"
    MIRROR_URL = (
        "https://raw.githubusercontent.com/vibedatascience/"
        "understat_players_aggregated/main/understat_players_aggregated_2014_td.csv"
    )

    def __init__(self, timeout: int = 30, allow_mirror: bool = True):
        self.timeout = timeout
        self.allow_mirror = allow_mirror

    @staticmethod
    def _extract_players_payload(text: str):
        patterns = [
            r"playersData\s*=\s*JSON\.parse\(\s*'((?:\\.|[^'])*)'\s*\)",
            r'playersData\s*=\s*JSON\.parse\(\s*"((?:\\.|[^"])*)"\s*\)',
        ]
        payload = None
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.S)
            if m:
                payload = m.group(1)
                break
        if payload is None:
            raise RuntimeError("Understat playersData non trovato nel markup corrente")

        payload = html.unescape(payload)
        candidates = [payload]
        try:
            candidates.append(codecs.decode(payload, "unicode_escape"))
        except Exception:
            pass
        try:
            candidates.append(bytes(payload, "utf-8").decode("unicode_escape"))
        except Exception:
            pass

        last_error = None
        for raw in candidates:
            try:
                data = json.loads(raw)
                # Some Understat helper libraries report a dict wrapper, while the
                # league page has historically exposed a bare list.
                if isinstance(data, dict) and isinstance(data.get("players"), list):
                    data = data["players"]
                if isinstance(data, list):
                    return data
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Understat playersData trovato ma non decodificabile: {last_error}")

    @staticmethod
    def _normalize(df: pd.DataFrame, season_start_year: int, source: str) -> pd.DataFrame:
        ren = {
            "player_name": "player",
            "team_title": "team_understat",
            "time": "minutes",
            "xG": "xg",
            "xA": "xa",
            "npxG": "npxg",
            "xGChain": "xg_chain",
            "xGBuildup": "xg_buildup",
            "yellow_cards": "yellow_cards",
            "red_cards": "red_cards",
        }
        out = df.rename(columns=ren).copy()
        numeric = [
            "games", "minutes", "goals", "assists", "shots", "key_passes",
            "xg", "xa", "npxg", "xg_chain", "xg_buildup", "yellow_cards", "red_cards",
        ]
        for c in numeric:
            if c in out:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        if "player" not in out or out.empty:
            raise RuntimeError("Understat payload valido ma privo di giocatori")
        out["source_stats"] = source
        out["understat_season"] = int(season_start_year)
        return out

    def _league_players_direct(self, season_start_year: int) -> pd.DataFrame:
        r = requests.get(
            self.URL.format(season=season_start_year),
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; FantaAuctionLab/1.0; +https://github.com/StoicPawn/fanta)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        r.raise_for_status()
        data = self._extract_players_payload(r.text)
        return self._normalize(pd.DataFrame(data), season_start_year, "understat-public")

    def _league_players_mirror(self, season_start_year: int) -> pd.DataFrame:
        r = requests.get(
            self.MIRROR_URL,
            timeout=max(self.timeout, 45),
            headers={"User-Agent": "FantaAuctionLab/1.0"},
        )
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        if "league" not in df or "year" not in df:
            raise RuntimeError("Understat mirror schema inatteso")
        year = pd.to_numeric(df["year"], errors="coerce")
        subset = df[df["league"].astype(str).eq("Serie_A") & year.eq(int(season_start_year))].copy()
        if subset.empty:
            raise RuntimeError(f"Understat mirror senza Serie_A {season_start_year}")
        return self._normalize(subset, season_start_year, "understat-github-mirror")

    def league_players(self, season_start_year: int) -> pd.DataFrame:
        direct_error = None
        try:
            return self._league_players_direct(season_start_year)
        except Exception as exc:
            direct_error = exc
        if self.allow_mirror:
            try:
                out = self._league_players_mirror(season_start_year)
                out["understat_direct_error"] = str(direct_error)[:300]
                return out
            except Exception as mirror_error:
                raise RuntimeError(
                    f"Understat direct fallito ({direct_error}); mirror fallito ({mirror_error})"
                ) from mirror_error
        raise direct_error
