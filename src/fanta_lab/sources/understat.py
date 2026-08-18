from __future__ import annotations

import codecs
import html
import json
import re

import pandas as pd
import requests


class UnderstatSource:
    """Public-data adapter for Understat league player aggregates.

    Understat embeds the league table as an escaped JSON payload in page scripts.  The
    exact escaping has changed over time (``\\xNN``/unicode escapes and whitespace), so
    parsing is deliberately tolerant while still requiring a valid JSON array.
    """

    URL = "https://understat.com/league/Serie_A/{season}"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

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

        # HTML entities may appear around escaped script content.  First unescape HTML,
        # then decode Javascript-style hexadecimal/unicode escapes.  latin1 round-trip
        # avoids corrupting already-decoded UTF-8 names.
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
                if isinstance(data, list):
                    return data
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Understat playersData trovato ma non decodificabile: {last_error}")

    def league_players(self, season_start_year: int) -> pd.DataFrame:
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
        df = pd.DataFrame(data)
        ren = {
            "player_name": "player",
            "team_title": "team_understat",
            "time": "minutes",
            "xG": "xg",
            "xA": "xa",
            "npxG": "npxg",
            "xGChain": "xg_chain",
            "xGBuildup": "xg_buildup",
        }
        df = df.rename(columns=ren)
        numeric = [
            "games", "minutes", "goals", "assists", "shots", "key_passes",
            "xg", "xa", "npxg", "xg_chain", "xg_buildup", "yellow_cards", "red_cards",
        ]
        for c in numeric:
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "player" not in df or df.empty:
            raise RuntimeError("Understat payload valido ma privo di giocatori")
        df["source_stats"] = "understat-public"
        df["understat_season"] = int(season_start_year)
        return df
