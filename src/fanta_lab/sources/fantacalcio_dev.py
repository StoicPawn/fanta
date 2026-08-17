from __future__ import annotations

import re
import pandas as pd


class FantacalcioDevSource:
    """Public, paginated Serie A fantasy archive on fantacalcio.dev.

    Tracked seasons currently span 2017-18 through 2025-26 and expose, per player,
    fantamedia, average vote, goals, assists and appearances. The adapter is deliberately
    HTML-defensive and treats this as independent historical enrichment.
    """

    BASE = "https://fantacalcio.dev/stagioni/{season}/players_in_seasons?page={page}"

    @staticmethod
    def _norm(c) -> str:
        s = str(c).strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s

    def page(self, season: str, page: int = 1) -> pd.DataFrame:
        tables = pd.read_html(self.BASE.format(season=season, page=page))
        if not tables:
            return pd.DataFrame()
        table = max(tables, key=lambda x: len(x))
        table.columns = [self._norm(c) for c in table.columns]
        ren = {
            "nome": "player",
            "fantamedia": "dev_fantamedia",
            "voto medio": "dev_avg_vote",
            "gol": "dev_goals",
            "assist": "dev_assists",
            "partite giocate": "dev_appearances",
            "stagioni": "dev_seasons_count",
            "ruoli": "dev_role",
        }
        table = table.rename(columns={c: ren[c] for c in table.columns if c in ren})
        if "player" not in table:
            return pd.DataFrame()
        keep = [c for c in ren.values() if c in table]
        out = table[keep].copy()
        out["player"] = out.player.astype(str).str.strip()
        for c in ["dev_fantamedia","dev_avg_vote","dev_goals","dev_assists","dev_appearances","dev_seasons_count"]:
            if c in out:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        out["dev_season"] = season
        out["fantacalcio_dev_source"] = f"fantacalcio.dev:{season}"
        return out.dropna(subset=["player"])

    def season(self, season: str, max_pages: int = 40) -> pd.DataFrame:
        frames=[]; seen=set()
        for p in range(1,max_pages+1):
            try:
                x=self.page(season,p)
            except Exception:
                break
            if x.empty:
                break
            keys=tuple(x.player.astype(str).tolist())
            if keys in seen:
                break
            seen.add(keys); frames.append(x)
            # Many site pages are shorter only on the final page.
            if len(x) < 10:
                break
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames,ignore_index=True).drop_duplicates("player",keep="first")

    def history(self, seasons: list[str]) -> pd.DataFrame:
        frames=[]
        for s in seasons:
            try:
                x=self.season(s)
                if len(x): frames.append(x)
            except Exception:
                continue
        return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
