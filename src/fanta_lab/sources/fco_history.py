from __future__ import annotations

import re
import unicodedata
import pandas as pd


class FCOHistoricalSource:
    """Public Fantacalcio-Online tables for historical fantasy context.

    The site exposes public quotation/stat tables with role, club, appearances and
    fantasy-relevant values. Markup may change, so parsing is defensive and this
    source is enrichment only, never roster authority.
    """

    BASE = "https://www.fantacalcio-online.com/it/serie-a/{season}/quotazioni"

    @staticmethod
    def _flat_col(c) -> str:
        if isinstance(c, tuple):
            c = " ".join(str(x) for x in c if str(x) != "nan")
        s = unicodedata.normalize("NFKD", str(c)).encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+", "_", s).strip("_")

    def fetch(self, season: str) -> pd.DataFrame:
        url = self.BASE.format(season=season)
        tables = pd.read_html(url)
        if not tables:
            return pd.DataFrame()
        # Prefer the widest table containing player-like rows.
        t = max(tables, key=lambda x: (len(x), len(x.columns)))
        t.columns = [self._flat_col(c) for c in t.columns]
        # Site labels vary; map by semantic fragments.
        def find(*parts):
            for c in t.columns:
                if all(p in c for p in parts):
                    return c
            return None
        name = find("nome") or find("calciatore") or find("giocatore")
        team = find("squadra") or find("club")
        role = find("ruolo") or next((c for c in t.columns if c in {"rt", "r"}), None)
        apps = find("pres") or find("presenze")
        avg = find("media", "voto") or next((c for c in t.columns if c in {"mv", "m_v"}), None)
        fanta = find("fanta", "media") or next((c for c in t.columns if c in {"fm", "f_m"}), None)
        quotation = find("quot") or find("kap")
        ren = {}
        for src, dst in [(name,"player"),(team,"team"),(role,"role_fco"),(apps,"fco_appearances"),(avg,"fco_avg_vote"),(fanta,"fco_fantamedia"),(quotation,"fco_quotation")]:
            if src: ren[src] = dst
        out = t.rename(columns=ren)
        if "player" not in out:
            return pd.DataFrame()
        keep = [c for c in ["player","team","role_fco","fco_appearances","fco_avg_vote","fco_fantamedia","fco_quotation"] if c in out]
        out = out[keep].copy()
        out["player"] = out.player.astype(str).str.strip()
        out = out[out.player.str.len().between(2,80)]
        for c in ["fco_appearances","fco_avg_vote","fco_fantamedia","fco_quotation"]:
            if c in out:
                out[c] = pd.to_numeric(out[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        out["fco_history_source"] = f"fantacalcio-online:{season}"
        return out.drop_duplicates("player")
