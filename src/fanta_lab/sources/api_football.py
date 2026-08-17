from __future__ import annotations

import requests
import pandas as pd


class APIFootballSource:
    """Optional API-Sports/API-Football free-tier enrichment.

    The free plan currently exposes all endpoint families with a daily quota. We use
    league discovery rather than hard-coding the Serie A ID, then cache-friendly league
    player pages and the league injury endpoint.
    """

    BASE = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str, timeout: int = 30):
        if not api_key:
            raise ValueError("API-Football key required")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        r=requests.get(self.BASE+path,params=params or {},headers={"x-apisports-key":self.api_key},timeout=self.timeout)
        r.raise_for_status(); data=r.json()
        if data.get("errors"):
            raise RuntimeError(str(data["errors"]))
        return data

    def serie_a(self, season: int) -> dict:
        data=self._get("/leagues",{"country":"Italy","season":season})
        for item in data.get("response",[]):
            league=item.get("league",{})
            if league.get("type") == "League" and str(league.get("name","")).lower() in {"serie a","serie a tim"}:
                cov=(item.get("seasons") or [{}])[-1].get("coverage",{})
                return {"id":league.get("id"),"name":league.get("name"),"coverage":cov}
        raise RuntimeError(f"Serie A not found for season {season}")

    @staticmethod
    def _flatten_player(item: dict) -> dict:
        p=item.get("player",{}); stats=item.get("statistics") or []
        # Prefer Serie A-style league stat block; if multiple blocks exist choose the one with most minutes.
        def mins(s):
            try:return float((s.get("games") or {}).get("minutes") or 0)
            except:return 0
        s=max(stats,key=mins) if stats else {}
        g=s.get("games",{}); goals=s.get("goals",{}); shots=s.get("shots",{}); passes=s.get("passes",{}); tackles=s.get("tackles",{}); cards=s.get("cards",{}); pen=s.get("penalty",{}); fouls=s.get("fouls",{}); dr=s.get("dribbles",{})
        return {
            "player":p.get("name"),"api_football_player_id":p.get("id"),"age":p.get("age"),"nationality":p.get("nationality"),
            "height":p.get("height"),"weight":p.get("weight"),"currently_injured":bool(p.get("injured",False)),
            "af_appearances":g.get("appearences"),"af_lineups":g.get("lineups"),"af_minutes":g.get("minutes"),"af_rating":g.get("rating"),
            "af_shots":shots.get("total"),"af_shots_on":shots.get("on"),"af_goals":goals.get("total"),"af_goals_conceded":goals.get("conceded"),
            "af_assists":goals.get("assists"),"af_saves":goals.get("saves"),"af_key_passes":passes.get("key"),"af_pass_accuracy":passes.get("accuracy"),
            "af_tackles":tackles.get("total"),"af_interceptions":tackles.get("interceptions"),"af_dribbles_attempts":dr.get("attempts"),"af_dribbles_success":dr.get("success"),
            "af_fouls_drawn":fouls.get("drawn"),"af_fouls_committed":fouls.get("committed"),"af_yellow":cards.get("yellow"),"af_red":cards.get("red"),
            "af_penalties_won":pen.get("won"),"af_penalties_committed":pen.get("commited"),"af_penalties_scored":pen.get("scored"),"af_penalties_missed":pen.get("missed"),"af_penalties_saved":pen.get("saved"),
            "api_football_source":"api-football",
        }

    def players(self, season: int, league_id: int | None = None, max_pages: int = 80) -> pd.DataFrame:
        league_id=league_id or int(self.serie_a(season)["id"])
        out=[]; page=1
        while page <= max_pages:
            data=self._get("/players",{"league":league_id,"season":season,"page":page})
            out += [self._flatten_player(x) for x in data.get("response",[])]
            paging=data.get("paging",{}); total=int(paging.get("total") or 1)
            if page>=total: break
            page+=1
        df=pd.DataFrame(out)
        if not df.empty:
            for c in [x for x in df if x.startswith("af_")]: df[c]=pd.to_numeric(df[c],errors="coerce")
        return df.drop_duplicates("player") if "player" in df else df

    def injuries(self, season: int, league_id: int | None = None) -> pd.DataFrame:
        league_id=league_id or int(self.serie_a(season)["id"])
        data=self._get("/injuries",{"league":league_id,"season":season})
        rows=[]
        for x in data.get("response",[]):
            p=x.get("player",{}); team=x.get("team",{}); fixture=x.get("fixture",{})
            rows.append({"player":p.get("name"),"api_football_player_id":p.get("id"),"injury_type":p.get("type"),"injury_reason":p.get("reason"),"injury_team":team.get("name"),"injury_fixture_date":fixture.get("date"),"currently_injured":True,"injury_source":"api-football"})
        return pd.DataFrame(rows).drop_duplicates("player") if rows else pd.DataFrame()
