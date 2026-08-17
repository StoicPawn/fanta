from __future__ import annotations

import io
from datetime import date
import requests
import numpy as np
import pandas as pd


class ClubEloSource:
    """Free ClubElo CSV API for current/historical team-strength ratings."""

    def __init__(self, timeout: int = 30):
        self.timeout=timeout

    def ranking(self, on_date: str | None = None) -> pd.DataFrame:
        d=on_date or date.today().isoformat()
        last=None
        for base in ("https://api.clubelo.com", "http://api.clubelo.com"):
            try:
                r=requests.get(f"{base}/{d}",timeout=self.timeout,headers={"User-Agent":"fanta-auction-lab/1.0"})
                r.raise_for_status(); df=pd.read_csv(io.StringIO(r.text))
                if len(df): return df
            except Exception as e: last=e
        if last: raise last
        return pd.DataFrame()

    def italy(self, on_date: str | None = None, levels: tuple[int,...]=(1,2)) -> pd.DataFrame:
        df=self.ranking(on_date)
        if df.empty:return df
        country_col=next((c for c in df if str(c).lower()=="country"),None)
        club_col=next((c for c in df if str(c).lower()=="club"),None)
        elo_col=next((c for c in df if str(c).lower()=="elo"),None)
        level_col=next((c for c in df if str(c).lower()=="level"),None)
        if not all([country_col,club_col,elo_col]): return pd.DataFrame()
        x=df[df[country_col].astype(str).str.upper().eq("ITA")].copy()
        if level_col and levels:x=x[pd.to_numeric(x[level_col],errors="coerce").isin(levels)]
        x=x.rename(columns={club_col:"team",elo_col:"team_elo"})
        x["team_elo"]=pd.to_numeric(x.team_elo,errors="coerce")
        med=float(x.team_elo.median()) if x.team_elo.notna().any() else 1600.0
        # Moderate multiplicative factor: roughly +/- 25% for a very large +/-400 Elo gap.
        x["team_elo_factor"]=np.exp((x.team_elo-med)/1600.0).clip(.72,1.38)
        x["clubelo_source"]=f"clubelo:{on_date or date.today().isoformat()}"
        keep=[c for c in ["team","team_elo","team_elo_factor",level_col,"clubelo_source"] if c]
        return x[keep].drop_duplicates("team")
